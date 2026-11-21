"""Aksi tulis di halaman web (khusus admin; login + CSRF dijaga di kosanhub/auth.py).

Validasi dan aturan bisnis memakai helper dan service yang sama dengan API JSON,
jadi hasilnya identik (mis. 1 kamar hanya boleh punya 1 kontrak aktif).
"""
from datetime import date

import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from kosanhub.auth import current_user
from sqlalchemy.exc import IntegrityError

from kosanhub import db
from kosanhub.errors import ApiError, ConflictError, NotFoundError, ValidationError
from kosanhub.models import Bill, BookingRequest, Contract, Property, Room, Tenant, User
from kosanhub.routes.tenants import _email, _phone
from kosanhub.routes.web import rupiah
from kosanhub.services.billing import outstanding_snapshot
from kosanhub.auth import change_password
from kosanhub.services.contracts import create_contract, end_contract, pay_bill
from kosanhub.services.bookings import approve_booking, reject_booking
from kosanhub.services.jobs import enqueue_billing_job
from kosanhub.utils import clean_str, parse_date, parse_int

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

MIN_PASSWORD = 8


def _f(name, label, type="text", **extra):
    return {"name": name, "label": label, "type": type, **extra}


def _form(title, fields, values, back, lead=None):
    return render_template("form.html", title=title, fields=fields, values=values, back=back, lead=lead)


def _attempt(action):
    """Jalankan action() lalu commit. Error validasi/bisnis tampil sebagai flash, bukan JSON."""
    try:
        message = action()
        db.session.commit()
    except ApiError as err:
        db.session.rollback()
        flash(err.message, "error")
        return False
    except IntegrityError:
        db.session.rollback()
        flash("Data bentrok dengan data yang sudah ada.", "error")
        return False
    flash(message, "ok")
    return True


def _blank_to_none(value):
    value = (value or "").strip()
    return value or None


# ---------- properti ----------
def _property_form(prop):
    fields = [_f("name", "Nama", required=True), _f("address", "Alamat", required=True)]
    values = {"name": prop.name, "address": prop.address} if prop else {}
    if request.method == "POST":
        values = request.form.to_dict()

        def action():
            target = prop or Property()
            target.name = clean_str(values.get("name"), "name", 120)
            target.address = clean_str(values.get("address"), "address")
            if prop is None:
                db.session.add(target)
            return "Properti disimpan."

        if _attempt(action):
            return redirect(url_for("web.properties"))
    title = f"Edit properti {prop.name}" if prop else "Tambah properti"
    return _form(title, fields, values, url_for("web.properties"))


@admin_bp.route("/properties/new", methods=["GET", "POST"])
def property_new():
    return _property_form(None)


@admin_bp.route("/properties/<int:prop_id>/edit", methods=["GET", "POST"])
def property_edit(prop_id):
    return _property_form(db.get_or_404(Property, prop_id))


@admin_bp.post("/properties/<int:prop_id>/delete")
def property_delete(prop_id):
    prop = db.get_or_404(Property, prop_id)

    def action():
        if any(r.contracts for r in prop.rooms):
            raise ConflictError("Properti memiliki kamar dengan riwayat kontrak, tidak dapat dihapus")
        db.session.delete(prop)
        return "Properti dihapus."

    _attempt(action)
    return redirect(url_for("web.properties"))


ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}


def _save_room_image(file):
    """Simpan file upload gambar kamar, kembalikan path relatif."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValidationError("Format gambar harus JPG, PNG, GIF, atau WebP")
    fname = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, "images", "rooms")
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, fname))
    return f"images/rooms/{fname}"


# ---------- kamar ----------
def _room_form(room):
    fields = []
    if room is None:
        props = db.session.scalars(db.select(Property).order_by(Property.name)).all()
        fields.append(_f("property_id", "Properti", "select", required=True, options=[(p.id, p.name) for p in props]))
    fields += [
        _f("number", "Nomor kamar", required=True),
        _f("monthly_price", "Harga per bulan (Rp)", "number", required=True, min=1),
        _f("image", "Gambar kamar (opsional)", "file", accept="image/*"),
    ]
    values = {"number": room.number, "monthly_price": room.monthly_price, "image": room.image} if room else {}
    if request.method == "POST":
        values = request.form.to_dict()
        if room and room.image and not values.get("image"):
            values["image"] = room.image

        def action():
            number = clean_str(values.get("number"), "number", 20)
            price = parse_int(values.get("monthly_price"), "monthly_price", minimum=1)
            if room is None:
                owner = parse_int(values.get("property_id"), "property_id", minimum=1)
                if db.session.get(Property, owner) is None:
                    raise NotFoundError("Properti tidak ditemukan")
            else:
                owner = room.property_id
            query = db.select(Room).where(Room.property_id == owner, Room.number == number)
            if room is not None:
                query = query.where(Room.id != room.id)
            if db.session.scalar(query) is not None:
                raise ConflictError(f"Nomor kamar {number} sudah ada di properti ini")
            # Handle image upload
            image_path = _save_room_image(request.files.get("image"))
            if room is None:
                new_room = Room(property_id=owner, number=number, monthly_price=price)
                if image_path:
                    new_room.image = image_path
                db.session.add(new_room)
            else:
                room.number = number
                room.monthly_price = price  # kontrak berjalan tidak berubah (harga dikunci saat kontrak dibuat)
                if image_path:
                    room.image = image_path
            return "Kamar disimpan."

        if _attempt(action):
            return redirect(url_for("web.rooms"))
    title = f"Edit kamar {room.number}" if room else "Tambah kamar"
    lead = room.kos_property.name if room else None
    return _form(title, fields, values, url_for("web.rooms"), lead)


@admin_bp.route("/rooms/new", methods=["GET", "POST"])
def room_new():
    return _room_form(None)


@admin_bp.route("/rooms/<int:room_id>/edit", methods=["GET", "POST"])
def room_edit(room_id):
    return _room_form(db.get_or_404(Room, room_id))


@admin_bp.post("/rooms/<int:room_id>/delete")
def room_delete(room_id):
    room = db.get_or_404(Room, room_id)

    def action():
        if room.contracts:
            raise ConflictError("Kamar memiliki riwayat kontrak, tidak dapat dihapus")
        db.session.delete(room)
        return "Kamar dihapus."

    _attempt(action)
    return redirect(url_for("web.rooms"))


# ---------- penyewa ----------
def _tenant_form(tenant):
    fields = [
        _f("name", "Nama", required=True),
        _f("phone", "Telepon", "tel", required=True, help="8-15 digit, boleh diawali +"),
        _f("email", "Email (opsional)", "email"),
    ]
    values = {"name": tenant.name, "phone": tenant.phone, "email": tenant.email or ""} if tenant else {}
    if request.method == "POST":
        values = request.form.to_dict()

        def action():
            target = tenant or Tenant()
            target.name = clean_str(values.get("name"), "name", 120)
            target.phone = _phone(values.get("phone"))
            target.email = _email(values.get("email"))
            if tenant is None:
                db.session.add(target)
            return "Penyewa disimpan."

        if _attempt(action):
            return redirect(url_for("web.tenants"))
    title = f"Edit penyewa {tenant.name}" if tenant else "Tambah penyewa"
    return _form(title, fields, values, url_for("web.tenants"))


@admin_bp.route("/tenants/new", methods=["GET", "POST"])
def tenant_new():
    return _tenant_form(None)


@admin_bp.route("/tenants/<int:tenant_id>/edit", methods=["GET", "POST"])
def tenant_edit(tenant_id):
    return _tenant_form(db.get_or_404(Tenant, tenant_id))


@admin_bp.post("/tenants/<int:tenant_id>/delete")
def tenant_delete(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)

    def action():
        if tenant.contracts:
            raise ConflictError("Penyewa memiliki riwayat kontrak, tidak dapat dihapus")
        db.session.delete(tenant)
        return "Penyewa dihapus."

    _attempt(action)
    return redirect(url_for("web.tenants"))


# ---------- kontrak (menyewakan kamar) ----------
@admin_bp.route("/contracts/new", methods=["GET", "POST"])
def contract_new():
    all_rooms = db.session.scalars(db.select(Room).order_by(Room.property_id, Room.number)).all()
    vacant = [r for r in all_rooms if r.active_contract is None]
    tenants = db.session.scalars(db.select(Tenant).order_by(Tenant.name)).all()
    fields = [
        _f(
            "room_id", "Kamar kosong", "select", required=True,
            options=[(r.id, f"{r.kos_property.name} / {r.number} ({rupiah(r.monthly_price)})") for r in vacant],
            prices={r.id: r.monthly_price for r in vacant},
        ),
        _f("tenant_id", "Penyewa", "select", required=True, options=[(t.id, t.name) for t in tenants]),
        _f("start_date", "Tanggal mulai", "date", required=True),
        _f("monthly_price", "Harga per bulan (kosongkan = harga kamar)", "number", min=1),
        _f("end_date", "Tanggal selesai (opsional)", "date"),
    ]
    values = {"room_id": request.args.get("room_id", ""), "start_date": date.today().isoformat()}
    if request.method == "POST":
        values = request.form.to_dict()

        def action():
            create_contract(
                room_id=parse_int(values.get("room_id"), "room_id", minimum=1),
                tenant_id=parse_int(values.get("tenant_id"), "tenant_id", minimum=1),
                start_date=parse_date(values.get("start_date"), "start_date"),
                monthly_price=parse_int(values["monthly_price"], "monthly_price", minimum=1)
                if _blank_to_none(values.get("monthly_price"))
                else None,
                end_date=parse_date(values["end_date"], "end_date") if _blank_to_none(values.get("end_date")) else None,
            )
            return "Kontrak dibuat, kamar disewakan."

        if _attempt(action):
            return redirect(url_for("web.contracts"))
    lead = None
    if not vacant:
        lead = "Tidak ada kamar kosong."
    elif not tenants:
        lead = "Belum ada penyewa. Tambahkan penyewa dulu."
    return _form("Buat kontrak sewa", fields, values, url_for("web.contracts"), lead)


@admin_bp.post("/contracts/<int:contract_id>/end")
def contract_end(contract_id):
    contract = db.get_or_404(Contract, contract_id)

    def action():
        end_contract(contract)
        return "Kontrak diakhiri."

    _attempt(action)
    return redirect(url_for("web.contracts"))


# ---------- pengajuan sewa ----------
@admin_bp.get("/bookings")
def bookings():
    status = request.args.get("status", BookingRequest.PENDING)
    query = db.select(BookingRequest).order_by(BookingRequest.id.desc())
    if status in (BookingRequest.PENDING, BookingRequest.APPROVED, BookingRequest.REJECTED):
        query = query.filter_by(status=status)
    else:
        status = "ALL"
    items = db.session.scalars(query).all()
    pending = db.session.scalar(
        db.select(db.func.count()).select_from(BookingRequest).filter_by(status=BookingRequest.PENDING)
    )
    return render_template("bookings.html", bookings=items, status=status, pending=pending)


@admin_bp.post("/bookings/<int:booking_id>/approve")
def booking_approve(booking_id):
    def action():
        booking = approve_booking(booking_id, current_user().id)
        return f"Pengajuan {booking.name} disetujui, kontrak #{booking.contract_id} dibuat."

    _attempt(action)
    return redirect(url_for("admin.bookings"))


@admin_bp.post("/bookings/<int:booking_id>/reject")
def booking_reject(booking_id):
    def action():
        booking = reject_booking(booking_id, current_user().id)
        return f"Pengajuan {booking.name} ditolak."

    _attempt(action)
    return redirect(url_for("admin.bookings"))


# ---------- pembayaran ----------
@admin_bp.route("/bills/<int:bill_id>/pay", methods=["GET", "POST"])
def bill_pay(bill_id):
    bill = db.get_or_404(Bill, bill_id)
    back = url_for("web.bills")
    if bill.status == Bill.PAID:
        flash("Tagihan sudah lunas.", "error")
        return redirect(back)
    today = date.today()
    snap = outstanding_snapshot(bill, today)
    values = {"amount": snap["outstanding"], "paid_on": today.isoformat(), "method": "TRANSFER"}
    if request.method == "POST":
        values = request.form.to_dict()

        def action():
            pay_bill(
                bill,
                parse_int(values.get("amount"), "amount", minimum=1),
                paid_on=parse_date(values.get("paid_on"), "paid_on"),
                method=clean_str(values.get("method") or "TRANSFER", "method", 30),
            )
            return "Pembayaran dicatat."

        if _attempt(action):
            return redirect(back)
    return render_template("pay_bill.html", bill=bill, snap=snap, values=values, back=back, today=today)


# ---------- job tagihan ----------
@admin_bp.post("/jobs/generate")
def job_generate():
    def action():
        today = date.today()
        job = enqueue_billing_job(
            parse_int(request.form.get("year") or today.year, "year"),
            parse_int(request.form.get("month") or today.month, "month"),
        )
        db.session.flush()
        return f"Job #{job.id} masuk antrean, akan diproses worker."

    _attempt(action)
    return redirect(url_for("web.jobs"))


# ---------- profile & user management ----------
@admin_bp.route("/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(user.password_hash, current_pw):
            flash("Password lama salah.", "error")
        elif len(new_pw) < MIN_PASSWORD:
            flash(f"Password baru minimal {MIN_PASSWORD} karakter.", "error")
        elif new_pw != confirm:
            flash("Konfirmasi password tidak sama.", "error")
        else:
            change_password(user, new_pw)
            session.clear()  # paksa login ulang di semua sesi browser ini
            flash("Password diubah. Silakan masuk dengan password baru.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("profile.html", user=user)


@admin_bp.get("/users")
def users_list():
    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return render_template("users.html", users=users, current=current_user())


@admin_bp.route("/users/new", methods=["GET", "POST"])
def users_new():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        def action():
            if not email:
                raise ValidationError("Email wajib diisi")
            if db.session.scalar(db.select(User.id).filter_by(email=email)) is not None:
                raise ConflictError(f"Email {email} sudah ada")
            if len(password) < MIN_PASSWORD:
                raise ValidationError(f"Password minimal {MIN_PASSWORD} karakter")
            db.session.add(User(email=email, password_hash=generate_password_hash(password)))
            return f"User {email} ditambahkan."
        
        if _attempt(action):
            return redirect(url_for("admin.users_list"))
    
    return render_template("form.html", 
        title="Tambah user", 
        fields=[
            _f("email", "Email", type="email", required=True),
            _f("password", "Password", type="password", required=True, help="Minimal 8 karakter"),
        ],
        values={},
        back=url_for("admin.users_list"))


@admin_bp.post("/users/<int:user_id>/delete")
def users_delete(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user().id:
        flash("Tidak bisa menghapus akun sendiri.", "error")
    else:
        def action():
            db.session.delete(user)
            return f"User {user.email} dihapus."
        _attempt(action)
    return redirect(url_for("admin.users_list"))

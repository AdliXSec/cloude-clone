"""Pengajuan sewa: ajukan (publik), setujui/tolak (admin), cek status (email + HP)."""
from datetime import date, datetime, timezone

from kosanhub import db
from kosanhub.errors import ConflictError, NotFoundError, ValidationError
from kosanhub.models import BookingRequest, Contract, Room, Tenant
from kosanhub.services.contracts import create_contract
from kosanhub.utils import clean_str, parse_date


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def submit_booking(room_id, name, email, phone, start_date, notes=None):
    """Simpan pengajuan PENDING. Kamar yang sedang terisi tidak bisa diajukan."""
    # Import di sini: kosanhub.routes.tenants memakai validator yang sama dengan API.
    from kosanhub.routes.tenants import _phone

    room = db.session.get(Room, room_id)
    if room is None:
        raise NotFoundError("Kamar tidak ditemukan")
    if room.active_contract is not None:
        raise ConflictError(f"Kamar {room.number} sedang terisi")

    name = clean_str(name, "Nama", 120)
    email = _email_required(email)
    phone = _phone(phone)
    start = parse_date(start_date, "Tanggal mulai")
    if start < date.today():
        raise ValidationError("Tanggal mulai tidak boleh sebelum hari ini")
    notes = clean_str(notes, "Catatan", 1000, required=False)

    duplicate = db.session.scalar(
        db.select(BookingRequest.id).filter_by(
            room_id=room_id, email=email, phone=phone, status=BookingRequest.PENDING
        )
    )
    if duplicate is not None:
        raise ConflictError("Pengajuan untuk kamar ini masih menunggu keputusan admin")

    booking = BookingRequest(
        room_id=room_id, name=name, email=email, phone=phone, start_date=start, notes=notes
    )
    db.session.add(booking)
    return booking


def _email_required(value):
    from kosanhub.routes.tenants import _email

    email = _email(value)
    if not email:
        raise ValidationError("email wajib diisi")
    return email.lower()


def _get_pending(booking_id):
    booking = db.session.scalar(
        db.select(BookingRequest).where(BookingRequest.id == booking_id).with_for_update()
    )
    if booking is None:
        raise NotFoundError("Pengajuan tidak ditemukan")
    if booking.status != BookingRequest.PENDING:
        raise ConflictError("Pengajuan ini sudah diputuskan")
    return booking


def find_tenant(email, phone):
    """Penyewa dikenali dari kombinasi email + HP (tanpa password)."""
    return db.session.scalar(
        db.select(Tenant).where(db.func.lower(Tenant.email) == email.lower(), Tenant.phone == phone)
    )


def approve_booking(booking_id, admin_id):
    """Buat Penyewa (bila belum ada) dan Kontrak ACTIVE. Aturan 1 kamar 1 kontrak dicek di sini."""
    booking = _get_pending(booking_id)
    tenant = find_tenant(booking.email, booking.phone)
    if tenant is None:
        tenant = Tenant(name=booking.name, phone=booking.phone, email=booking.email)
        db.session.add(tenant)
        db.session.flush()
    contract = create_contract(booking.room_id, tenant.id, booking.start_date)
    db.session.flush()
    booking.status = BookingRequest.APPROVED
    booking.decided_at = _now()
    booking.decided_by = admin_id
    booking.tenant_id = tenant.id
    booking.contract_id = contract.id
    return booking


def reject_booking(booking_id, admin_id):
    booking = _get_pending(booking_id)
    booking.status = BookingRequest.REJECTED
    booking.decided_at = _now()
    booking.decided_by = admin_id
    return booking


def lookup_status(email, phone):
    """Data milik penyewa untuk email + HP. None bila tidak ada pengajuan maupun penyewa yang cocok."""
    from kosanhub.routes.tenants import _phone

    email = (email or "").strip().lower()
    try:
        phone = _phone(phone)
    except ValidationError:
        return None
    if not email:
        return None

    bookings = db.session.scalars(
        db.select(BookingRequest)
        .where(BookingRequest.email == email, BookingRequest.phone == phone)
        .order_by(BookingRequest.id.desc())
    ).all()
    tenant = find_tenant(email, phone)
    if not bookings and tenant is None:
        return None

    contracts = tenant.contracts if tenant else []
    contracts = sorted(contracts, key=lambda c: (c.status != Contract.ACTIVE, -c.id))
    bills = [b for c in contracts for b in c.bills]
    bills.sort(key=lambda b: (b.period_year, b.period_month, b.id))
    payments = [p for b in bills for p in b.payments]
    payments.sort(key=lambda p: (p.paid_on, p.id), reverse=True)
    return {
        "name": tenant.name if tenant else bookings[0].name,
        "bookings": bookings,
        "contracts": contracts,
        "bills": bills,
        "payments": payments,
    }

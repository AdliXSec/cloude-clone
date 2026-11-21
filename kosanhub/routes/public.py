"""Portal publik tanpa login: lihat properti & kamar, ajukan sewa, cek status.

Aksi POST dijaga token CSRF (kosanhub/auth.py). Tidak ada akun penyewa; penyewa
dikenali lewat kombinasi email + HP.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from kosanhub import db
from kosanhub.errors import ApiError
from kosanhub.models import Property, Room
from kosanhub.services.bookings import lookup_status, submit_booking
from kosanhub.routes.web import _bill_rows
from datetime import date

public_bp = Blueprint("public", __name__)


@public_bp.get("/")
def home():
    props = db.session.scalars(db.select(Property).order_by(Property.name)).all()
    return render_template("public_home.html", properties=props)


@public_bp.get("/kamar/<int:room_id>")
def room_detail(room_id):
    room = db.get_or_404(Room, room_id)
    return render_template("public_room.html", room=room)


@public_bp.route("/kamar/<int:room_id>/ajukan", methods=["GET", "POST"])
def book(room_id):
    room = db.get_or_404(Room, room_id)
    values = {}
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            submit_booking(
                room.id,
                values.get("name"),
                values.get("email"),
                values.get("phone"),
                values.get("start_date"),
                values.get("notes"),
            )
            db.session.commit()
        except ApiError as err:
            db.session.rollback()
            flash(err.message, "error")
            return render_template("public_book.html", room=room, values=values, today=date.today()), err.status_code
        flash("Pengajuan terkirim. Admin akan meninjau; cek statusnya dengan email dan nomor HP Anda.", "ok")
        return redirect(url_for("public.status"))
    return render_template("public_book.html", room=room, values=values, today=date.today())


@public_bp.route("/status", methods=["GET", "POST"])
def status():
    if request.method == "POST":
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        data = lookup_status(email, phone)
        if data is None:
            flash("Data tidak ditemukan. Periksa email dan nomor HP yang Anda pakai saat mengajukan.", "error")
            return render_template("public_status.html", email=email, phone=phone, data=None), 404
        rows = _bill_rows(data["bills"], date.today())
        return render_template("public_status.html", email=email, phone=phone, data=data, rows=rows)
    return render_template("public_status.html", email="", phone="", data=None)

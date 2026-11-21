"""Halaman web (Jinja2). Hanya membaca data; perubahan data tetap lewat API."""
from datetime import date, timedelta

from flask import Blueprint, render_template

from kosanhub import db
from kosanhub.models import Bill, BillingJob, Contract, Payment, Property, Room, Tenant
from kosanhub.services.billing import outstanding_snapshot

web_bp = Blueprint("web", __name__)

WIB = timedelta(hours=7)  # database menyimpan UTC


@web_bp.app_template_filter("rupiah")
def rupiah(value):
    return "Rp " + f"{int(value or 0):,}".replace(",", ".")


@web_bp.app_template_filter("tanggal")
def tanggal(value):
    return value.strftime("%d/%m/%Y") if value else "-"


@web_bp.app_template_filter("waktu_wib")
def waktu_wib(value):
    return (value + WIB).strftime("%d/%m/%Y %H:%M") if value else "-"


def _bill_rows(bills, as_of):
    """Gabungkan tagihan dengan denda per as_of. Tagihan lunas memakai angka yang sudah dibekukan."""
    rows = []
    for bill in bills:
        if bill.status == Bill.UNPAID:
            snap = outstanding_snapshot(bill, as_of)
            fee, total, remaining, late = snap["late_fee"], snap["total_due"], snap["outstanding"], snap["days_late"]
        else:
            fee, total, remaining, late = bill.late_fee, bill.total, 0, 0
        rows.append({"bill": bill, "late_fee": fee, "total": total, "remaining": remaining, "days_late": late})
    return rows


def _arrears(as_of):
    bills = db.session.scalars(
        db.select(Bill).where(Bill.status == Bill.UNPAID, Bill.due_date < as_of).order_by(Bill.due_date, Bill.id)
    ).all()
    return _bill_rows(bills, as_of)


@web_bp.get("/dashboard")
def dashboard():
    today = date.today()
    rooms = db.session.scalars(db.select(Room)).all()
    arrears = _arrears(today)
    unpaid = db.session.scalar(db.select(db.func.count()).select_from(Bill).where(Bill.status == Bill.UNPAID))
    stats = {
        "properties": db.session.scalar(db.select(db.func.count()).select_from(Property)),
        "rooms_total": len(rooms),
        "rooms_occupied": sum(1 for r in rooms if r.active_contract),
        "tenants": db.session.scalar(db.select(db.func.count()).select_from(Tenant)),
        "active_contracts": db.session.scalar(
            db.select(db.func.count()).select_from(Contract).where(Contract.status == Contract.ACTIVE)
        ),
        "unpaid_bills": unpaid,
        "arrears_count": len(arrears),
        "arrears_total": sum(r["remaining"] for r in arrears),
    }
    return render_template("dashboard.html", stats=stats, arrears=arrears[:5], today=today)


@web_bp.get("/properties")
def properties():
    items = db.session.scalars(db.select(Property).order_by(Property.id)).all()
    return render_template("properties.html", properties=items)


@web_bp.get("/rooms")
def rooms():
    items = db.session.scalars(db.select(Room).order_by(Room.property_id, Room.number)).all()
    return render_template("rooms.html", rooms=items)


@web_bp.get("/tenants")
def tenants():
    items = db.session.scalars(db.select(Tenant).order_by(Tenant.id)).all()
    return render_template("tenants.html", tenants=items)


@web_bp.get("/contracts")
def contracts():
    items = db.session.scalars(db.select(Contract).order_by(Contract.id)).all()
    return render_template("contracts.html", contracts=items)


@web_bp.get("/bills")
def bills():
    today = date.today()
    items = db.session.scalars(
        db.select(Bill).order_by(Bill.period_year, Bill.period_month, Bill.id)
    ).all()
    return render_template("bills.html", rows=_bill_rows(items, today), today=today)


@web_bp.get("/payments")
def payments():
    items = db.session.scalars(
        db.select(Payment).order_by(Payment.paid_on.desc(), Payment.id.desc())
    ).all()
    return render_template("payments.html", payments=items, total=sum(p.amount for p in items))


@web_bp.get("/arrears")
def arrears():
    today = date.today()
    rows = _arrears(today)
    return render_template("arrears.html", rows=rows, today=today, total=sum(r["remaining"] for r in rows))


@web_bp.get("/jobs")
def jobs():
    items = db.session.scalars(db.select(BillingJob).order_by(BillingJob.id.desc())).all()
    return render_template("jobs.html", jobs=items)

"""Kontrak sewa & pembayaran."""
from datetime import date

from sqlalchemy.exc import IntegrityError

from kosanhub import db
from kosanhub.errors import ConflictError, NotFoundError, ValidationError
from kosanhub.models import Bill, Contract, Payment, Room, Tenant
from kosanhub.services.billing import outstanding_snapshot


def create_contract(room_id, tenant_id, start_date, monthly_price=None, end_date=None):
    """Aturan bisnis 1: satu kamar hanya boleh punya satu kontrak ACTIVE."""
    # Kunci baris kamar supaya dua request bersamaan tidak sama-sama lolos cek (MySQL/PostgreSQL).
    room = db.session.scalar(db.select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        raise NotFoundError("Kamar tidak ditemukan")
    if db.session.get(Tenant, tenant_id) is None:
        raise NotFoundError("Penyewa tidak ditemukan")
    if end_date is not None and end_date <= start_date:
        raise ValidationError("end_date harus setelah start_date")

    active = db.session.scalar(
        db.select(Contract).filter_by(room_id=room_id, status=Contract.ACTIVE)
    )
    if active is not None:
        raise ConflictError(f"Kamar {room.number} masih memiliki kontrak aktif (id {active.id})")

    price = monthly_price if monthly_price is not None else room.monthly_price
    if price <= 0:
        raise ValidationError("monthly_price harus lebih dari 0")

    contract = Contract(
        room_id=room_id,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        monthly_price=price,
        status=Contract.ACTIVE,
    )
    try:
        with db.session.begin_nested():
            db.session.add(contract)
            db.session.flush()
    except IntegrityError:
        # Jaring pengaman terakhir: UNIQUE(active_room_id) di database menolak kontrak aktif ganda.
        raise ConflictError(f"Kamar {room.number} masih memiliki kontrak aktif")
    return contract


def end_contract(contract, end_date=None):
    if contract.status == Contract.ENDED:
        raise ConflictError("Kontrak sudah berakhir")
    end_date = end_date or date.today()
    if end_date < contract.start_date:
        raise ValidationError("end_date tidak boleh sebelum start_date")
    contract.end_date = end_date
    contract.status = Contract.ENDED
    return contract


def pay_bill(bill, amount, paid_on=None, method="TRANSFER"):
    """Catat pembayaran. Denda dihitung per tanggal bayar lalu dibekukan di tagihan."""
    paid_on = paid_on or date.today()
    if amount <= 0:
        raise ValidationError("amount harus lebih dari 0")
    if bill.status == Bill.PAID:
        raise ConflictError("Tagihan sudah lunas")

    snap = outstanding_snapshot(bill, paid_on)
    if amount > snap["outstanding"]:
        raise ValidationError(
            f"Pembayaran melebihi sisa tagihan (sisa {snap['outstanding']})"
        )

    bill.late_fee = snap["late_fee"]
    bill.total = snap["total_due"]
    payment = Payment(bill=bill, amount=amount, paid_on=paid_on, method=method)
    db.session.add(payment)
    db.session.flush()
    if bill.paid_amount >= bill.total:
        bill.status = Bill.PAID
        bill.paid_at = paid_on
    return payment

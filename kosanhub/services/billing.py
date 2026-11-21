"""
Logika aturan bisnis tagihan KosanHub (murni + yang menyentuh DB).

Aturan:
  2. Tagihan bulan pertama proporsional sesuai tanggal masuk.
  3. Denda keterlambatan 2% per minggu (dihitung per minggu yang sudah dimulai), maks 10%.
  4. Tagihan tidak boleh terbit dua kali untuk periode yang sama.
"""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError

from kosanhub import db
from kosanhub.errors import ConflictError, ValidationError
from kosanhub.models import Bill

LATE_FEE_PERCENT_PER_WEEK = 2
LATE_FEE_MAX_PERCENT = 10


def _rupiah(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def prorated_amount(monthly_price, start_date):
    """Tagihan bulan masuk = harga * (sisa hari termasuk hari masuk / jumlah hari di bulan itu)."""
    dim = days_in_month(start_date.year, start_date.month)
    remaining_days = dim - start_date.day + 1
    return _rupiah(Decimal(monthly_price) * remaining_days / dim)


def late_fee_percent(days_late):
    """1-7 hari = 2%, 8-14 = 4%, ... dibatasi maksimal 10%."""
    if days_late <= 0:
        return 0
    weeks_started = (days_late + 6) // 7
    return min(weeks_started * LATE_FEE_PERCENT_PER_WEEK, LATE_FEE_MAX_PERCENT)


def late_fee_amount(base_amount, days_late):
    return _rupiah(Decimal(base_amount) * late_fee_percent(days_late) / 100)


def days_late(due_date, as_of):
    return max((as_of - due_date).days, 0)


def base_amount_for_period(contract, year, month):
    """Nominal dasar tagihan periode tsb, atau None bila kontrak tidak berlaku di periode itu."""
    period = (year, month)
    start = (contract.start_date.year, contract.start_date.month)
    if period < start:
        return None
    if contract.end_date and period > (contract.end_date.year, contract.end_date.month):
        return None
    if period == start:
        return prorated_amount(contract.monthly_price, contract.start_date)
    return contract.monthly_price


def due_date_for(contract, year, month, due_day):
    due = date(year, month, min(due_day, days_in_month(year, month)))
    if (year, month) == (contract.start_date.year, contract.start_date.month):
        due = max(due, contract.start_date)
    return due


def create_bill(contract, year, month, due_day=10):
    """Terbitkan tagihan satu periode. Raise ConflictError bila periode sudah pernah ditagih."""
    if not 1 <= month <= 12:
        raise ValidationError("month harus 1-12")
    if year < 2000 or year > 2100:
        raise ValidationError("year di luar rentang yang wajar")

    base = base_amount_for_period(contract, year, month)
    if base is None:
        raise ValidationError("Kontrak tidak berlaku pada periode tersebut")

    existing = db.session.scalar(
        db.select(Bill).filter_by(contract_id=contract.id, period_year=year, period_month=month)
    )
    if existing is not None:
        raise ConflictError(f"Tagihan {year:04d}-{month:02d} untuk kontrak {contract.id} sudah ada")

    bill = Bill(
        contract_id=contract.id,
        period_year=year,
        period_month=month,
        base_amount=base,
        late_fee=0,
        total=base,
        due_date=due_date_for(contract, year, month, due_day),
    )
    try:
        with db.session.begin_nested():
            db.session.add(bill)
    except IntegrityError:
        # Jaga-jaga bila dua proses menerbitkan bersamaan: unique constraint di DB menang.
        raise ConflictError(f"Tagihan {year:04d}-{month:02d} untuk kontrak {contract.id} sudah ada")
    return bill


def outstanding_snapshot(bill, as_of):
    """Hitung denda & sisa tagihan per tanggal tertentu tanpa mengubah data."""
    late = days_late(bill.due_date, as_of)
    fee = late_fee_amount(bill.base_amount, late)
    total = bill.base_amount + fee
    return {
        "days_late": late,
        "late_percent": late_fee_percent(late),
        "late_fee": fee,
        "total_due": total,
        "outstanding": max(total - bill.paid_amount, 0),
    }

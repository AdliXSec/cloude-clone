"""Tagihan, tunggakan, dan pembayaran."""
from datetime import date

from flask import Blueprint, current_app, jsonify, request

from kosanhub import db
from kosanhub.errors import NotFoundError
from kosanhub.models import Bill, Contract, Payment
from kosanhub.services.billing import create_bill, outstanding_snapshot
from kosanhub.services.contracts import pay_bill
from kosanhub.utils import clean_str, json_body, parse_date, parse_int, require

bills_bp = Blueprint("bills", __name__)
payments_bp = Blueprint("payments", __name__)


def _as_of():
    value = request.args.get("as_of")
    return parse_date(value, "as_of") if value else date.today()


def _bill_view(bill, as_of):
    body = bill.to_dict()
    if bill.status == Bill.UNPAID:
        body.update(outstanding_snapshot(bill, as_of))
    return body


@bills_bp.get("")
def list_bills():
    query = db.select(Bill).order_by(Bill.period_year, Bill.period_month, Bill.id)
    if request.args.get("contract_id"):
        query = query.filter_by(contract_id=parse_int(request.args["contract_id"], "contract_id"))
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"].upper())
    as_of = _as_of()
    return jsonify([_bill_view(b, as_of) for b in db.session.scalars(query).all()])


@bills_bp.post("")
def issue_bill():
    """Terbitkan satu tagihan secara manual (sinkron). Untuk massal pakai /api/jobs."""
    data = json_body()
    require(data, "contract_id", "year", "month")
    contract = db.session.get(Contract, parse_int(data["contract_id"], "contract_id", minimum=1))
    if contract is None:
        raise NotFoundError("Kontrak tidak ditemukan")
    bill = create_bill(
        contract,
        parse_int(data["year"], "year"),
        parse_int(data["month"], "month"),
        due_day=current_app.config["BILL_DUE_DAY"],
    )
    db.session.commit()
    return jsonify(bill.to_dict()), 201


@bills_bp.get("/arrears")
def arrears():
    """Daftar tunggakan: tagihan UNPAID yang sudah melewati jatuh tempo per tanggal as_of."""
    as_of = _as_of()
    bills = db.session.scalars(
        db.select(Bill).where(Bill.status == Bill.UNPAID, Bill.due_date < as_of).order_by(Bill.due_date)
    ).all()
    items = []
    for bill in bills:
        view = _bill_view(bill, as_of)
        view["tenant"] = bill.contract.tenant.name
        view["room"] = bill.contract.room.number
        view["property"] = bill.contract.room.kos_property.name
        items.append(view)
    return jsonify(
        {
            "as_of": as_of.isoformat(),
            "count": len(items),
            "total_outstanding": sum(i["outstanding"] for i in items),
            "items": items,
        }
    )


@bills_bp.get("/<int:bill_id>")
def get_bill(bill_id):
    bill = db.session.get(Bill, bill_id)
    if bill is None:
        raise NotFoundError("Tagihan tidak ditemukan")
    body = _bill_view(bill, _as_of())
    body["payments"] = [p.to_dict() for p in bill.payments]
    return jsonify(body)


@payments_bp.get("")
def list_payments():
    query = db.select(Payment).order_by(Payment.id)
    if request.args.get("bill_id"):
        query = query.filter_by(bill_id=parse_int(request.args["bill_id"], "bill_id"))
    return jsonify([p.to_dict() for p in db.session.scalars(query).all()])


@payments_bp.post("")
def create_payment():
    data = json_body()
    require(data, "bill_id", "amount")
    bill = db.session.get(Bill, parse_int(data["bill_id"], "bill_id", minimum=1))
    if bill is None:
        raise NotFoundError("Tagihan tidak ditemukan")
    payment = pay_bill(
        bill,
        parse_int(data["amount"], "amount", minimum=1),
        paid_on=parse_date(data["paid_on"], "paid_on") if data.get("paid_on") else None,
        method=clean_str(data.get("method") or "TRANSFER", "method", 30),
    )
    db.session.commit()
    return jsonify({"payment": payment.to_dict(), "bill": bill.to_dict()}), 201

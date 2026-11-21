"""Kontrak sewa."""
from flask import Blueprint, jsonify, request

from kosanhub import db
from kosanhub.errors import NotFoundError
from kosanhub.models import Contract
from kosanhub.services.contracts import create_contract, end_contract
from kosanhub.utils import json_body, parse_date, parse_int, require

contracts_bp = Blueprint("contracts", __name__)


def _get(contract_id):
    contract = db.session.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError("Kontrak tidak ditemukan")
    return contract


@contracts_bp.get("")
def list_contracts():
    query = db.select(Contract).order_by(Contract.id)
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status.upper())
    return jsonify([c.to_dict() for c in db.session.scalars(query).all()])


@contracts_bp.post("")
def create():
    data = json_body()
    require(data, "room_id", "tenant_id", "start_date")
    contract = create_contract(
        room_id=parse_int(data["room_id"], "room_id", minimum=1),
        tenant_id=parse_int(data["tenant_id"], "tenant_id", minimum=1),
        start_date=parse_date(data["start_date"], "start_date"),
        monthly_price=parse_int(data["monthly_price"], "monthly_price", minimum=1)
        if data.get("monthly_price") is not None
        else None,
        end_date=parse_date(data["end_date"], "end_date") if data.get("end_date") else None,
    )
    db.session.commit()
    return jsonify(contract.to_dict()), 201


@contracts_bp.get("/<int:contract_id>")
def get(contract_id):
    contract = _get(contract_id)
    body = contract.to_dict()
    body["bills"] = [b.to_dict() for b in contract.bills]
    return jsonify(body)


@contracts_bp.post("/<int:contract_id>/end")
def end(contract_id):
    contract = _get(contract_id)
    data = request.get_json(silent=True) or {}
    end_date = parse_date(data["end_date"], "end_date") if data.get("end_date") else None
    end_contract(contract, end_date)
    db.session.commit()
    return jsonify(contract.to_dict())

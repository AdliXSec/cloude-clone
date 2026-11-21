"""CRUD data penyewa."""
import re

from flask import Blueprint, jsonify

from kosanhub import db
from kosanhub.errors import ConflictError, NotFoundError, ValidationError
from kosanhub.models import Contract, Tenant
from kosanhub.utils import clean_str, json_body

tenants_bp = Blueprint("tenants", __name__)

_PHONE = re.compile(r"^\+?[0-9]{8,15}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _phone(value):
    phone = clean_str(value, "phone", 30).replace(" ", "").replace("-", "")
    if not _PHONE.match(phone):
        raise ValidationError("phone harus 8-15 digit angka")
    return phone


def _email(value):
    email = clean_str(value, "email", 120, required=False)
    if email and not _EMAIL.match(email):
        raise ValidationError("email tidak valid")
    return email


def _get(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Penyewa tidak ditemukan")
    return tenant


@tenants_bp.get("")
def list_tenants():
    tenants = db.session.scalars(db.select(Tenant).order_by(Tenant.id)).all()
    return jsonify([t.to_dict() for t in tenants])


@tenants_bp.post("")
def create_tenant():
    data = json_body()
    tenant = Tenant(
        name=clean_str(data.get("name"), "name", 120),
        phone=_phone(data.get("phone")),
        email=_email(data.get("email")),
    )
    db.session.add(tenant)
    db.session.commit()
    return jsonify(tenant.to_dict()), 201


@tenants_bp.get("/<int:tenant_id>")
def get_tenant(tenant_id):
    tenant = _get(tenant_id)
    body = tenant.to_dict()
    body["contracts"] = [c.to_dict() for c in tenant.contracts]
    return jsonify(body)


@tenants_bp.put("/<int:tenant_id>")
def update_tenant(tenant_id):
    tenant = _get(tenant_id)
    data = json_body()
    if "name" in data:
        tenant.name = clean_str(data["name"], "name", 120)
    if "phone" in data:
        tenant.phone = _phone(data["phone"])
    if "email" in data:
        tenant.email = _email(data["email"])
    db.session.commit()
    return jsonify(tenant.to_dict())


@tenants_bp.delete("/<int:tenant_id>")
def delete_tenant(tenant_id):
    tenant = _get(tenant_id)
    if db.session.scalar(db.select(Contract.id).filter_by(tenant_id=tenant.id).limit(1)) is not None:
        raise ConflictError("Penyewa memiliki riwayat kontrak, tidak dapat dihapus")
    db.session.delete(tenant)
    db.session.commit()
    return "", 204

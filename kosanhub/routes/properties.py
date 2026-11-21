"""CRUD properti dan kamar."""
from flask import Blueprint, jsonify

from kosanhub import db
from kosanhub.errors import ConflictError, NotFoundError
from kosanhub.models import Contract, Property, Room
from kosanhub.utils import clean_str, json_body, parse_int

properties_bp = Blueprint("properties", __name__)
rooms_bp = Blueprint("rooms", __name__)


def _get_property(property_id):
    prop = db.session.get(Property, property_id)
    if prop is None:
        raise NotFoundError("Properti tidak ditemukan")
    return prop


def _get_room(room_id):
    room = db.session.get(Room, room_id)
    if room is None:
        raise NotFoundError("Kamar tidak ditemukan")
    return room


# ---------- properti ----------
@properties_bp.get("")
def list_properties():
    props = db.session.scalars(db.select(Property).order_by(Property.id)).all()
    return jsonify([p.to_dict() for p in props])


@properties_bp.post("")
def create_property():
    data = json_body()
    prop = Property(name=clean_str(data.get("name"), "name", 120), address=clean_str(data.get("address"), "address"))
    db.session.add(prop)
    db.session.commit()
    return jsonify(prop.to_dict()), 201


@properties_bp.get("/<int:property_id>")
def get_property(property_id):
    prop = _get_property(property_id)
    body = prop.to_dict()
    body["rooms"] = [r.to_dict() for r in prop.rooms]
    return jsonify(body)


@properties_bp.put("/<int:property_id>")
def update_property(property_id):
    prop = _get_property(property_id)
    data = json_body()
    if "name" in data:
        prop.name = clean_str(data["name"], "name", 120)
    if "address" in data:
        prop.address = clean_str(data["address"], "address")
    db.session.commit()
    return jsonify(prop.to_dict())


@properties_bp.delete("/<int:property_id>")
def delete_property(property_id):
    prop = _get_property(property_id)
    if any(r.contracts for r in prop.rooms):
        raise ConflictError("Properti memiliki kamar dengan riwayat kontrak, tidak dapat dihapus")
    db.session.delete(prop)
    db.session.commit()
    return "", 204


# ---------- kamar ----------
@rooms_bp.get("")
def list_rooms():
    rooms = db.session.scalars(db.select(Room).order_by(Room.property_id, Room.number)).all()
    return jsonify([r.to_dict() for r in rooms])


@rooms_bp.post("")
def create_room():
    data = json_body()
    property_id = parse_int(data.get("property_id"), "property_id", minimum=1)
    _get_property(property_id)
    number = clean_str(data.get("number"), "number", 20)
    duplicate = db.session.scalar(db.select(Room).filter_by(property_id=property_id, number=number))
    if duplicate is not None:
        raise ConflictError(f"Nomor kamar {number} sudah ada di properti ini")
    room = Room(
        property_id=property_id,
        number=number,
        monthly_price=parse_int(data.get("monthly_price"), "monthly_price", minimum=1),
    )
    db.session.add(room)
    db.session.commit()
    return jsonify(room.to_dict()), 201


@rooms_bp.get("/<int:room_id>")
def get_room(room_id):
    return jsonify(_get_room(room_id).to_dict())


@rooms_bp.put("/<int:room_id>")
def update_room(room_id):
    room = _get_room(room_id)
    data = json_body()
    if "number" in data:
        number = clean_str(data["number"], "number", 20)
        duplicate = db.session.scalar(
            db.select(Room).where(Room.property_id == room.property_id, Room.number == number, Room.id != room.id)
        )
        if duplicate is not None:
            raise ConflictError(f"Nomor kamar {number} sudah ada di properti ini")
        room.number = number
    if "monthly_price" in data:
        # Tidak mengubah kontrak berjalan: harga kontrak dikunci saat kontrak dibuat.
        room.monthly_price = parse_int(data["monthly_price"], "monthly_price", minimum=1)
    db.session.commit()
    return jsonify(room.to_dict())


@rooms_bp.delete("/<int:room_id>")
def delete_room(room_id):
    room = _get_room(room_id)
    has_contract = db.session.scalar(db.select(Contract.id).filter_by(room_id=room.id).limit(1))
    if has_contract is not None:
        raise ConflictError("Kamar memiliki riwayat kontrak, tidak dapat dihapus")
    db.session.delete(room)
    db.session.commit()
    return "", 204

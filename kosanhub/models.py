"""Model database KosanHub."""
from datetime import datetime, timezone

from sqlalchemy import event

from kosanhub import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    rooms = db.relationship("Room", back_populates="kos_property", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "room_count": len(self.rooms),
        }


class Room(db.Model):
    __tablename__ = "rooms"
    __table_args__ = (db.UniqueConstraint("property_id", "number", name="uq_room_property_number"),)

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    number = db.Column(db.String(20), nullable=False)
    monthly_price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    kos_property = db.relationship("Property", back_populates="rooms")
    contracts = db.relationship("Contract", back_populates="room")

    @property
    def active_contract(self):
        return next((c for c in self.contracts if c.status == "ACTIVE"), None)

    def to_dict(self):
        return {
            "id": self.id,
            "property_id": self.property_id,
            "number": self.number,
            "monthly_price": self.monthly_price,
            "image": self.image,
            "occupied": self.active_contract is not None,
        }


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    contracts = db.relationship("Contract", back_populates="tenant")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "phone": self.phone, "email": self.email}


class Contract(db.Model):
    __tablename__ = "contracts"

    ACTIVE = "ACTIVE"
    ENDED = "ENDED"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    monthly_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False, default=ACTIVE, index=True)
    # Penjaga aturan bisnis 1 di level database: berisi room_id selama kontrak ACTIVE, NULL bila
    # tidak. UNIQUE mengizinkan banyak NULL (MySQL & SQLite), sehingga hanya satu kontrak ACTIVE
    # per kamar yang bisa ada, bahkan bila dua request lolos cek di level aplikasi bersamaan.
    # Nilainya diisi otomatis oleh listener di bawah, jangan diisi manual.
    active_room_id = db.Column(db.Integer, nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    room = db.relationship("Room", back_populates="contracts")
    tenant = db.relationship("Tenant", back_populates="contracts")
    bills = db.relationship("Bill", back_populates="contract")

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "tenant_id": self.tenant_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "monthly_price": self.monthly_price,
            "status": self.status,
        }


@event.listens_for(Contract, "before_insert")
@event.listens_for(Contract, "before_update")
def _sync_active_room_id(mapper, connection, target):
    target.active_room_id = target.room_id if target.status == Contract.ACTIVE else None


class Bill(db.Model):
    __tablename__ = "bills"
    # Aturan bisnis 4: satu kontrak hanya boleh punya satu tagihan per periode.
    __table_args__ = (
        db.UniqueConstraint("contract_id", "period_year", "period_month", name="uq_bill_contract_period"),
    )

    UNPAID = "UNPAID"
    PAID = "PAID"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False, index=True)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)
    base_amount = db.Column(db.Integer, nullable=False)
    late_fee = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default=UNPAID, index=True)
    paid_at = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    contract = db.relationship("Contract", back_populates="bills")
    payments = db.relationship("Payment", back_populates="bill")

    @property
    def paid_amount(self):
        return sum(p.amount for p in self.payments)

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "period": f"{self.period_year:04d}-{self.period_month:02d}",
            "base_amount": self.base_amount,
            "late_fee": self.late_fee,
            "total": self.total,
            "paid_amount": self.paid_amount,
            "due_date": self.due_date.isoformat(),
            "status": self.status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    paid_on = db.Column(db.Date, nullable=False)
    method = db.Column(db.String(30), nullable=False, default="TRANSFER")
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    bill = db.relationship("Bill", back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "bill_id": self.bill_id,
            "amount": self.amount,
            "paid_on": self.paid_on.isoformat(),
            "method": self.method,
        }


class BookingRequest(db.Model):
    """Pengajuan sewa dari publik (tanpa login). Admin setuju/tolak → kontrak + penyewa dibuat."""

    __tablename__ = "booking_requests"

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(10), nullable=False, default=PENDING, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=True)

    room = db.relationship("Room", foreign_keys=[room_id])
    decider = db.relationship("User", foreign_keys=[decided_by])
    tenant = db.relationship("Tenant")
    contract = db.relationship("Contract")

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "start_date": self.start_date.isoformat(),
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "tenant_id": self.tenant_id,
            "contract_id": self.contract_id,
        }


class BillingJob(db.Model):
    """Antrean berbasis database: dibuat oleh API, diproses oleh worker."""

    __tablename__ = "billing_jobs"

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    id = db.Column(db.Integer, primary_key=True)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(12), nullable=False, default=PENDING, index=True)
    created_count = db.Column(db.Integer, nullable=False, default=0)
    skipped_count = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "period": f"{self.period_year:04d}-{self.period_month:02d}",
            "status": self.status,
            "created_count": self.created_count,
            "skipped_count": self.skipped_count,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

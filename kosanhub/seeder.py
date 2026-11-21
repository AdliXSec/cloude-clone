"""Seed data dummy untuk development dan testing."""
import os
import click
from datetime import date, timedelta

from kosanhub import db
from kosanhub.auth import ensure_admin
from kosanhub.models import Property, Room, Tenant, Contract


# Default khusus development. Production wajib menimpa lewat ADMIN_EMAIL / ADMIN_PASSWORD.
DEFAULT_ADMIN_EMAIL = "admin@gmail.com"
DEFAULT_ADMIN_PASSWORD = "password"


def _seed_admin():
    email = os.getenv("ADMIN_EMAIL") or DEFAULT_ADMIN_EMAIL
    password = os.getenv("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD
    if ensure_admin(email, password):
        click.echo(f"Admin dibuat: {email}")
        if password == DEFAULT_ADMIN_PASSWORD:
            click.echo("PERINGATAN: memakai password default dev. Set ADMIN_PASSWORD untuk production.")
    else:
        click.echo(f"Admin {email} sudah ada.")


def register_cli(app):
    @app.cli.command("create-admin")
    def create_admin():
        """Buat akun admin (idempoten; tidak menimpa password yang sudah ada)."""
        _seed_admin()

    @app.cli.command()
    def seed():
        """Buat admin, lalu data dummy: properti, kamar, penyewa, kontrak."""
        # Idempoten: aman dijalankan otomatis tiap container app start.
        _seed_admin()
        if db.session.scalar(db.select(Property.id).limit(1)) is not None:
            click.echo("Seeder dilewati: data sudah ada.")
            return

        click.echo("Seeding database...")

        # Properti
        kos1 = Property(name="Kos Megah Pusat", address="Jl. Merdeka No. 10")
        kos2 = Property(name="Kos Nyaman Dulu", address="Jl. Ahmad Yani No. 5")
        db.session.add_all([kos1, kos2])
        db.session.flush()

        # Kamar di Kos Megah
        for i in range(1, 6):
            room = Room(property_id=kos1.id, number=f"101-{i}", monthly_price=500000)
            db.session.add(room)
        db.session.flush()

        # Kamar di Kos Nyaman
        for i in range(1, 4):
            room = Room(property_id=kos2.id, number=f"A-{i}", monthly_price=400000)
            db.session.add(room)
        db.session.flush()

        # Penyewa
        tenants = [
            Tenant(name="Budi Santoso", phone="+62812345678", email="budi@example.com"),
            Tenant(name="Siti Nurhaliza", phone="+62898765432", email="siti@example.com"),
            Tenant(name="Andi Wijaya", phone="+6281999999", email="andi@example.com"),
            Tenant(name="Maya Putri", phone="+6282111111", email="maya@example.com"),
        ]
        db.session.add_all(tenants)
        db.session.flush()

        # Kontrak
        today = date.today()
        contracts = [
            Contract(
                room_id=1, tenant_id=tenants[0].id, start_date=today - timedelta(days=30),
                monthly_price=500000, status=Contract.ACTIVE
            ),
            Contract(
                room_id=2, tenant_id=tenants[1].id, start_date=today - timedelta(days=15),
                monthly_price=500000, status=Contract.ACTIVE
            ),
            Contract(
                room_id=6, tenant_id=tenants[2].id, start_date=today - timedelta(days=5),
                monthly_price=400000, status=Contract.ACTIVE
            ),
        ]
        db.session.add_all(contracts)
        db.session.commit()

        click.echo(
            f"✓ {len(kos1.rooms) + len(kos2.rooms)} kamar, "
            f"{len(tenants)} penyewa, "
            f"{len(contracts)} kontrak aktif dibuat"
        )

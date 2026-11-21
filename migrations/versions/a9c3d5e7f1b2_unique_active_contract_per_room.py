"""satu kamar hanya boleh punya satu kontrak ACTIVE (constraint di database)

Revision ID: a9c3d5e7f1b2
Revises: f7a1c2d3e4b5
Create Date: 2026-11-22 03:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a9c3d5e7f1b2"
down_revision = "f7a1c2d3e4b5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contracts") as batch:
        batch.add_column(sa.Column("active_room_id", sa.Integer(), nullable=True))

    # Isi dari data lama. Bila sudah terlanjur ada kontrak ACTIVE ganda di satu kamar, hanya yang
    # id terkecil yang diisi supaya migrasi tidak gagal; sisanya perlu dirapikan admin.
    op.execute(
        "UPDATE contracts SET active_room_id = room_id "
        "WHERE status = 'ACTIVE' AND id IN ("
        "  SELECT first_id FROM ("
        "    SELECT MIN(id) AS first_id FROM contracts WHERE status = 'ACTIVE' GROUP BY room_id"
        "  ) AS t)"
    )

    with op.batch_alter_table("contracts") as batch:
        batch.create_unique_constraint("uq_contract_active_room", ["active_room_id"])


def downgrade():
    with op.batch_alter_table("contracts") as batch:
        batch.drop_constraint("uq_contract_active_room", type_="unique")
        batch.drop_column("active_room_id")

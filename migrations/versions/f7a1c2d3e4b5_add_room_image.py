"""add room image column

Revision ID: f7a1c2d3e4b5
Revises: e5a2b8c1d3f4
Create Date: 2026-11-21 17:38:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a1c2d3e4b5"
down_revision = "e5a2b8c1d3f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rooms", sa.Column("image", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("rooms", "image")

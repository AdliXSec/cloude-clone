"""add booking_requests (pengajuan sewa publik)

Revision ID: e5a2b8c1d3f4
Revises: c41d7e9a2b10
Create Date: 2026-11-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a2b8c1d3f4'
down_revision = 'c41d7e9a2b10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('booking_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('decided_by', sa.Integer(), nullable=True),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('contract_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('booking_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_booking_requests_room_id'), ['room_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_booking_requests_status'), ['status'], unique=False)


def downgrade():
    with op.batch_alter_table('booking_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_booking_requests_status'))
        batch_op.drop_index(batch_op.f('ix_booking_requests_room_id'))

    op.drop_table('booking_requests')

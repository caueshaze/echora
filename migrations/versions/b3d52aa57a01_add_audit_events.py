"""Add append-only administrative audit events."""
from alembic import op
import sqlalchemy as sa

revision = 'b3d52aa57a01'
down_revision = '55306b189242'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('operation_id', sa.String(36), nullable=False),
        sa.Column('actor_id', sa.String(36), nullable=False),
        sa.Column('actor_role', sa.String(32), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('resource_type', sa.String(32), nullable=False),
        sa.Column('resource_id', sa.String(64)),
        sa.Column('school_id', sa.Integer()),
        sa.Column('result', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('operation_id', 'action', name='uq_audit_operation_action'),
    )


def downgrade():
    op.drop_table('audit_events')

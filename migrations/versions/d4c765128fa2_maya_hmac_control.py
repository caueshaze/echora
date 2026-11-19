"""Add shared Maya HMAC identity; no identity or cutover is activated."""
from alembic import op
import sqlalchemy as sa

revision = 'd4c765128fa2'
down_revision = 'b7c84f219c20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('maya_hmac_control',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key_identity', sa.String(64), nullable=False),
        sa.Column('legacy_barrier', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint('id = 1', name='ck_maya_hmac_control_singleton'))


def downgrade():
    raise RuntimeError('Downgrade do controle HMAC exige procedimento operacional revisado')

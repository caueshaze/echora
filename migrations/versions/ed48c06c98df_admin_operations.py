"""Store transactional administrative retry markers."""
from alembic import op
import sqlalchemy as sa

revision = 'ed48c06c98df'
down_revision = 'c63f9471dacc'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('admin_operations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('actor_id', sa.String(36), nullable=False),
        sa.Column('key_digest', sa.String(64), nullable=False),
        sa.Column('request_digest', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('actor_id', 'key_digest', name='uq_admin_operation_actor_key'))

def downgrade():
    op.drop_table('admin_operations')

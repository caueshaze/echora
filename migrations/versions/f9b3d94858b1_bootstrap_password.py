"""Require a password change for explicitly bootstrapped accounts."""
from alembic import op
import sqlalchemy as sa

revision = 'f9b3d94858b1'
down_revision = 'ed48c06c98df'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('admin_operations') as batch:
        batch.alter_column('request_digest', existing_type=sa.String(64), nullable=True)

def downgrade():
    op.execute("UPDATE admin_operations SET request_digest = '' WHERE request_digest IS NULL")
    with op.batch_alter_table('admin_operations') as batch:
        batch.alter_column('request_digest', existing_type=sa.String(64), nullable=False)
    op.drop_column('users', 'must_change_password')

"""Add a backwards-compatible version to Maya idempotency digests."""
from alembic import context, op
import sqlalchemy as sa

revision = 'b7c84f219c20'
down_revision = 'a7d41e6b2c90'
branch_labels = None
depends_on = None


def upgrade():
    # Old application versions omit this column and therefore keep writing v1.
    op.add_column('maya_questions', sa.Column('request_digest_version', sa.String(16), nullable=False,
                                            server_default='legacy-v1'))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError('Downgrade exige verificação online dos digests')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Prevent a concurrent v2 insert between the safety check and DROP.
        bind.exec_driver_sql('LOCK TABLE maya_questions IN ACCESS EXCLUSIVE MODE')
    if bind.execute(sa.text("SELECT 1 FROM maya_questions WHERE request_digest_version <> 'legacy-v1' LIMIT 1")).first():
        raise RuntimeError('Downgrade recusado: existem digests não legados')
    op.drop_column('maya_questions', 'request_digest_version')

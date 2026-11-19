"""Add school-scoped permissions and one-use revelation requests."""
from alembic import op
import sqlalchemy as sa

revision = 'c63f9471dacc'
down_revision = 'b3d52aa57a01'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('reveal_permissions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=False),
        sa.Column('permission', sa.String(32), nullable=False),
        sa.UniqueConstraint('user_id', 'school_id', 'permission', name='uq_reveal_permission'),
        sa.CheckConstraint("permission IN ('reveal_request', 'reveal_approve')", name='ck_reveal_permission'))
    op.create_table('reveal_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('feedback_id', sa.Integer, sa.ForeignKey('feedbacks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requester_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('approver_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('threat', sa.Text, nullable=False), sa.Column('necessity', sa.Text, nullable=False),
        sa.Column('proportionality', sa.Text, nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True)), sa.Column('consumed_at', sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table('reveal_requests')
    op.drop_table('reveal_permissions')

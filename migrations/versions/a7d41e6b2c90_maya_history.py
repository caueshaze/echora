"""Persist encrypted Maya analyses and contextual questions."""
from alembic import op
import sqlalchemy as sa

revision = 'a7d41e6b2c90'
down_revision = 'f9b3d94858b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('maya_analyses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('requester_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id')),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('content_encrypted', sa.Text(), nullable=False),
        sa.Column('nonce', sa.String(32), nullable=False),
        sa.Column('feedback_count', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date()), sa.Column('period_end', sa.Date()),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for name in ('requester_id', 'school_id', 'created_at'):
        op.create_index('ix_maya_analyses_' + name, 'maya_analyses', [name])
    op.create_table('maya_conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('analysis_id', sa.String(36), sa.ForeignKey('maya_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('analysis_id', 'user_id', name='uq_maya_conversation_analysis_user'))
    for name in ('analysis_id', 'user_id'):
        op.create_index('ix_maya_conversations_' + name, 'maya_conversations', [name])
    op.create_table('maya_questions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('maya_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_key', sa.String(64), nullable=False), sa.Column('request_digest', sa.String(64), nullable=False),
        sa.Column('question_encrypted', sa.Text(), nullable=False), sa.Column('question_nonce', sa.String(32), nullable=False),
        sa.Column('answer_encrypted', sa.Text()), sa.Column('answer_nonce', sa.String(32)),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('reservation_id', sa.String(36)),
        sa.Column('quota_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_maya_question_user_key'))
    for name in ('conversation_id', 'user_id'):
        op.create_index('ix_maya_questions_' + name, 'maya_questions', [name])
    op.create_table('maya_daily_quotas',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('quota_date', sa.Date(), primary_key=True),
        sa.Column('consumed', sa.Integer(), nullable=False))


def downgrade():
    for table in ('maya_daily_quotas', 'maya_questions', 'maya_conversations', 'maya_analyses'):
        op.drop_table(table)

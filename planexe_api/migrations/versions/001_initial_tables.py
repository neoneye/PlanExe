"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-19
PURPOSE: Initial database migration for PlanExe - creates all core tables for plan persistence
SRP and DRY check: Pass - Single responsibility of database schema creation
"""

"""Initial PlanExe database tables

Revision ID: 001
Revises:
Create Date: 2025-09-19 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial PlanExe database schema"""

    # Create plans table
    op.create_table('plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('llm_model', sa.String(length=255), nullable=True),
        sa.Column('speed_vs_detail', sa.String(length=50), nullable=False),
        sa.Column('openrouter_api_key_hash', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('progress_percentage', sa.Integer(), nullable=True),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('output_dir', sa.String(length=500), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Float(), nullable=True),
        sa.Column('actual_duration_minutes', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_plan_id'), 'plans', ['plan_id'], unique=True)
    op.create_index(op.f('ix_plans_user_id'), 'plans', ['user_id'], unique=False)

    # Create llm_interactions table
    op.create_table('llm_interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('llm_model', sa.String(length=255), nullable=False),
        sa.Column('stage', sa.String(length=100), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('prompt_metadata', sa.JSON(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_interactions_plan_id'), 'llm_interactions', ['plan_id'], unique=False)

    # Create plan_files table
    op.create_table('plan_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('generated_by_stage', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_files_plan_id'), 'plan_files', ['plan_id'], unique=False)

    # Create plan_metrics table
    op.create_table('plan_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('total_llm_calls', sa.Integer(), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('plan_complexity_score', sa.Float(), nullable=True),
        sa.Column('plan_completeness_score', sa.Float(), nullable=True),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('peak_memory_mb', sa.Float(), nullable=True),
        sa.Column('cpu_time_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_metrics_plan_id'), 'plan_metrics', ['plan_id'], unique=False)

    # Set default values for existing columns
    op.execute("ALTER TABLE plans ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE plans ALTER COLUMN speed_vs_detail SET DEFAULT 'ALL_DETAILS_BUT_SLOW'")
    op.execute("ALTER TABLE plans ALTER COLUMN progress_percentage SET DEFAULT 0")
    op.execute("ALTER TABLE plans ALTER COLUMN progress_message SET DEFAULT ''")
    op.execute("ALTER TABLE plans ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP")

    op.execute("ALTER TABLE llm_interactions ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE llm_interactions ALTER COLUMN started_at SET DEFAULT CURRENT_TIMESTAMP")

    op.execute("ALTER TABLE plan_files ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP")

    op.execute("ALTER TABLE plan_metrics ALTER COLUMN total_llm_calls SET DEFAULT 0")
    op.execute("ALTER TABLE plan_metrics ALTER COLUMN total_tokens_used SET DEFAULT 0")
    op.execute("ALTER TABLE plan_metrics ALTER COLUMN total_cost_usd SET DEFAULT 0.0")
    op.execute("ALTER TABLE plan_metrics ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP")


def downgrade() -> None:
    """Drop all PlanExe tables"""
    op.drop_table('plan_metrics')
    op.drop_table('plan_files')
    op.drop_table('llm_interactions')
    op.drop_table('plans')
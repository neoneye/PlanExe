"""
Author: Claude Code (Sonnet 4)
Date: 2025-10-01
PURPOSE: Add plan_content table and performance indexes for Option 1 database-first architecture
SRP and DRY check: Pass - Single responsibility of adding content persistence infrastructure
"""

"""Add plan_content table and performance indexes

Revision ID: 002
Revises: 001
Create Date: 2025-10-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add plan_content table for storing Luigi task outputs.
    Add performance indexes for fast retrieval during plan generation.

    This migration supports Option 1 (database-first architecture) where each
    Luigi task writes content directly to the database during execution.
    """

    # Create plan_content table (if it doesn't exist)
    # This table stores the actual content of plan files for persistence
    op.create_table('plan_content',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('stage', sa.String(length=100), nullable=True),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_size_bytes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Add indexes for plan_content table
    # These indexes are critical for performance when Luigi tasks write/read content
    op.create_index(
        'idx_plan_content_plan_id',
        'plan_content',
        ['plan_id'],
        unique=False
    )

    # Composite index for fast filename lookups within a plan
    op.create_index(
        'idx_plan_content_plan_id_filename',
        'plan_content',
        ['plan_id', 'filename'],
        unique=False  # Allow multiple versions of same file
    )

    # Stage-based filtering (useful for debugging specific pipeline stages)
    op.create_index(
        'idx_plan_content_stage',
        'plan_content',
        ['stage'],
        unique=False
    )

    # Set default timestamps
    op.execute("ALTER TABLE plan_content ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP")

    print("✅ Migration 002: plan_content table and indexes created successfully")


def downgrade() -> None:
    """
    Remove plan_content table and all associated indexes.

    WARNING: This will delete all persisted plan content!
    """
    op.drop_index('idx_plan_content_stage', table_name='plan_content')
    op.drop_index('idx_plan_content_plan_id_filename', table_name='plan_content')
    op.drop_index('idx_plan_content_plan_id', table_name='plan_content')
    op.drop_table('plan_content')

    print("⚠️ Migration 002 downgrade: plan_content table dropped")

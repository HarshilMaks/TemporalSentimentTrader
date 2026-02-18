"""Add quality scoring fields and performance indexes to reddit_posts table.

Revision ID: 001_add_quality_scoring
Revises: 6aeb58d1fa26
Create Date: 2026-02-18 10:00:00.000000

This migration adds:
1. is_quality boolean field (indexed) - True if quality_score >= 50
2. Index on quality_score (Float) for range queries
3. Composite index (is_quality, created_at) for fast quality-filtered queries
4. Ensures quality fields are properly indexed for production performance
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_quality_scoring'
down_revision: Union[str, Sequence[str], None] = '6aeb58d1fa26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade: Add quality scoring fields and performance indexes.
    
    Changes:
    1. Add is_quality boolean field (indexed)
    2. Add quality_score index for range queries
    3. Add composite (is_quality, created_at) index for quality filtering
    4. Ensure created_at has index for time-based queries
    """
    # Add is_quality column if it doesn't exist
    # This column is derived: True if quality_score >= 50, else False
    try:
        op.add_column('reddit_posts',
            sa.Column('is_quality', sa.Boolean(), nullable=False, server_default='false')
        )
    except Exception:
        # Column might already exist, continue silently
        pass
    
    # Create index on quality_score for range queries
    # Allows fast filtering like: WHERE quality_score > 50
    op.create_index(
        'idx_quality_score',
        'reddit_posts',
        ['quality_score'],
        if_not_exists=True
    )
    
    # Create composite index on (is_quality, created_at) for filtering + sorting
    # Enables: WHERE is_quality=true ORDER BY created_at DESC
    # This is the most common query pattern for quality-filtered feeds
    op.create_index(
        'idx_quality_created',
        'reddit_posts',
        ['is_quality', 'created_at'],
        if_not_exists=True
    )
    
    # Ensure created_at has index for time-based queries
    # Allows: WHERE created_at > now() - interval '7 days'
    try:
        op.create_index(
            'idx_created_at',
            'reddit_posts',
            ['created_at'],
            if_not_exists=True
        )
    except Exception:
        # Index might already exist
        pass


def downgrade() -> None:
    """
    Downgrade: Remove quality scoring fields and performance indexes.
    
    Removes:
    1. Composite (is_quality, created_at) index
    2. Quality score index
    3. is_quality boolean field
    """
    # Drop composite index first (most specific)
    op.drop_index('idx_quality_created', table_name='reddit_posts', if_exists=True)
    
    # Drop quality score index
    op.drop_index('idx_quality_score', table_name='reddit_posts', if_exists=True)
    
    # Drop created_at index if we added it (be careful, other queries might use it)
    # Only drop if you're sure it's not used elsewhere
    # op.drop_index('idx_created_at', table_name='reddit_posts', if_exists=True)
    
    # Drop is_quality column
    op.drop_column('reddit_posts', 'is_quality')

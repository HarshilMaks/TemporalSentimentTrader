"""Add quality scoring fields to reddit_posts table.

Revision ID: 003_add_quality_fields
Revises: 6aeb58d1fa26
Create Date: 2026-02-18 12:00:00.000000

This migration adds the quality scoring columns that were defined in the model
but not yet created in the database:
- quality_score (Float): 0-100 quality rating
- quality_tier (String): categorical tier (poor, fair, good, excellent)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003_add_quality_fields'
down_revision: Union[str, Sequence[str], None] = '001_add_quality_scoring'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quality scoring columns to reddit_posts."""
    # Add quality_score column (0-100 float)
    op.add_column('reddit_posts',
        sa.Column('quality_score', sa.Float(), nullable=False, server_default='0.0')
    )
    
    # Add quality_tier column (categorical: poor, fair, good, excellent)
    op.add_column('reddit_posts',
        sa.Column('quality_tier', sa.String(length=20), nullable=False, server_default='fair')
    )


def downgrade() -> None:
    """Remove quality scoring columns from reddit_posts."""
    op.drop_column('reddit_posts', 'quality_tier')
    op.drop_column('reddit_posts', 'quality_score')

"""add_reddit_post_enhanced_fields

Revision ID: 6aeb58d1fa26
Revises: 77e7abb8d3a8
Create Date: 2026-02-15 14:39:55.037536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aeb58d1fa26'
down_revision: Union[str, Sequence[str], None] = '77e7abb8d3a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add enhanced metadata fields to reddit_posts table."""
    # Add upvote_ratio column (0.0-1.0 percentage)
    op.add_column('reddit_posts', 
        sa.Column('upvote_ratio', sa.Float(), nullable=True, server_default='0.0')
    )
    
    # Add is_self column (True=text post, False=link post)
    op.add_column('reddit_posts', 
        sa.Column('is_self', sa.Boolean(), nullable=True, server_default='true')
    )
    
    # Add link_flair_text column (post flair tag)
    op.add_column('reddit_posts', 
        sa.Column('link_flair_text', sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    """Remove enhanced metadata fields from reddit_posts table."""
    op.drop_column('reddit_posts', 'link_flair_text')
    op.drop_column('reddit_posts', 'is_self')
    op.drop_column('reddit_posts', 'upvote_ratio')

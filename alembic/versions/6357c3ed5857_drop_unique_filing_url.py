"""drop_unique_filing_url

Revision ID: 6357c3ed5857
Revises: 004_add_insider_trades
Create Date: 2026-02-28 14:10:42.693571

"""
from typing import Sequence, Union
from alembic import op

revision: str = '6357c3ed5857'
down_revision: Union[str, Sequence[str], None] = '004_add_insider_trades'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('insider_trades_filing_url_key', 'insider_trades', type_='unique')
    op.create_index('idx_insider_filing_url', 'insider_trades', ['filing_url'])


def downgrade() -> None:
    op.drop_index('idx_insider_filing_url', table_name='insider_trades')
    op.create_unique_constraint('insider_trades_filing_url_key', 'insider_trades', ['filing_url'])

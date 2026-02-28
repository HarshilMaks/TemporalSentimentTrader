"""Add insider_trades and predictions tables.

Revision ID: 004_add_insider_trades
Revises: 002_optimize_quality_scoring
Create Date: 2026-02-27 12:41:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "004_add_insider_trades"
down_revision = "002_optimize_quality_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insider_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("insider_name", sa.String(200), nullable=False),
        sa.Column("insider_title", sa.String(100), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("dollar_value", sa.Float(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("filing_url", sa.String(500), nullable=True, unique=True),
        sa.Column("source", sa.String(10), nullable=False, server_default="SEC"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_insider_ticker_date", "insider_trades", ["ticker", "transaction_date"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("xgb_confidence", sa.Float(), nullable=True),
        sa.Column("lgb_confidence", sa.Float(), nullable=True),
        sa.Column("tft_confidence", sa.Float(), nullable=True),
        sa.Column("feature_snapshot_id", sa.String(36), nullable=True),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prediction_ticker_date", "predictions", ["ticker", "predicted_at"])


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("insider_trades")

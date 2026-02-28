"""InsiderTrade ORM model — SEC Form 4 and SEBI PIT filings."""

from sqlalchemy import Column, Integer, String, Float, BigInteger, Date, DateTime, Index
from sqlalchemy.sql import func

from backend.database.config import Base


class InsiderTrade(Base):
    __tablename__ = "insider_trades"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False)
    insider_name = Column(String(200), nullable=False)
    insider_title = Column(String(100), nullable=True)
    transaction_type = Column(String(10), nullable=False)  # BUY or SELL
    shares = Column(BigInteger, nullable=True)
    dollar_value = Column(Float, nullable=True)
    transaction_date = Column(Date, nullable=False)
    filing_date = Column(Date, nullable=True)
    filing_url = Column(String(500), nullable=True)
    source = Column(String(10), nullable=False, default="SEC")  # SEC or SEBI

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_insider_ticker_date", "ticker", "transaction_date"),
        Index("idx_insider_filing_url", "filing_url"),
    )

    def __repr__(self):
        return f"<InsiderTrade {self.transaction_type} {self.ticker} by {self.insider_name}>"

from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY, Index, Float
from sqlalchemy.sql import func
from backend.database.config import Base

class RedditPost(Base):
    __tablename__ = "reddit_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    subreddit = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text)
    author = Column(String(50))
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    tickers = Column(ARRAY(String), server_default='{}')
    sentiment_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    url = Column(String(500))
    
    __table_args__ = (
        Index('idx_tickers', 'tickers', postgresql_using='gin'),
        Index('idx_created_at', 'created_at'),
    )

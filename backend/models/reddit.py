from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY, Index, Float, Numeric, Boolean
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
    upvote_ratio = Column(Float, default=0.0)  # NEW: 0.0-1.0 upvote percentage
    is_self = Column(Boolean, default=True)  # NEW: True=text post, False=link
    link_flair_text = Column(String(100))  # NEW: Post flair tag
    tickers = Column(ARRAY(String), server_default='{}')
    sentiment_score = Column(Numeric(precision=5, scale=4), default=0.0)
    quality_score = Column(Float, default=0.0, index=True)  # 0-100 quality assessment (indexed)
    quality_tier = Column(String(20), default='fair')  # poor/fair/good/excellent
    is_quality = Column(Boolean, default=False, index=True)  # True if quality_score >= 50
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    url = Column(String(500))
    
    __table_args__ = (
        Index('idx_tickers', 'tickers', postgresql_using='gin'),
        Index('idx_created_at', 'created_at'),
        Index('idx_quality_created', 'is_quality', 'created_at'),  # Composite index for filtering
        Index('idx_quality_score', 'quality_score'),  # High-cardinality quality score
    )

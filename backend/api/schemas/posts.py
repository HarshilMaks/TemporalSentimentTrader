from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PostResponse(BaseModel):
    id: int
    title: str
    tickers: list[str]
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1")
    score: int
    url: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class PostListResponse(BaseModel):
    total: int  # Total posts in DB (not just this page)
    page: int
    page_size: int
    posts: list[PostResponse]


class PostByTickerResponse(BaseModel):
    ticker: str
    count: int
    posts: list[dict]


class TickerSentiment(BaseModel):
    ticker: str
    sentiment: str  # bullish/bearish/neutral/No data
    avg_score: float = Field(..., ge=-1.0, le=1.0)
    post_count: int = Field(..., ge=0)
    total_engagement: int = Field(..., ge=0)

class TrendingTicker(BaseModel):
    ticker: str
    mentions: int

class TrendingResponse(BaseModel):
    trending: list[TrendingTicker]

class QualityAnalyticsResponse(BaseModel):
    """Response model for quality analytics endpoint."""
    total: int = Field(..., ge=0, description="Total posts in time window")
    avg_quality: float = Field(..., ge=0.0, le=100.0, description="Average quality score")
    high_quality_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of high-quality posts")
    low_quality_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of low-quality posts")
    quality_distribution: dict[str, int] = Field(..., description="Count by tier (poor/fair/good/excellent)")
    quality_threshold: int = Field(..., ge=0, le=100, description="Quality threshold used")
    time_window_hours: int = Field(..., ge=1, description="Time window in hours")

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
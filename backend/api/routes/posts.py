from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text, func
from backend.models.reddit import RedditPost
from backend.database.config import get_db
from backend.api.schemas.posts import PostListResponse, PostByTickerResponse, TrendingResponse, TickerSentiment
from backend.api.middleware.rate_limit import check_rate_limit
from backend.config.rate_limits import RATE_LIMITS, get_period_seconds

router = APIRouter(prefix="/posts", tags=["posts"])


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT DEPENDENCY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# Each endpoint has a corresponding rate limit function.
# These encapsulate the rate limit configuration for that endpoint.
# Usage: add async def limit_X(req: Request) and then use Depends(limit_X)
#
# Why separate functions?
# 1. Cleaner code (doesn't clutter endpoint function signature)
# 2. Reusable (same limit function can be used by multiple endpoints if needed)
# 3. Configurable (change limits in one place, update function, done)


async def rate_limit_posts_list(request: Request):
    """
    Rate limit: GET /posts/ endpoint
    
    Limit: 100 requests per minute per IP address
    
    Rationale:
    - This is a simple paginated SELECT query
    - Relatively cheap (indexed sort by score, offset/limit)
    - Common operation users will call frequently
    - No side effects, safe to have higher limits
    
    Endpoint cost: 🟢 LOW (cacheable reads)
    """
    config = RATE_LIMITS["posts:list"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:list",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_ticker(request: Request):
    """
    Rate limit: GET /posts/ticker/{ticker} endpoint
    
    Limit: 100 requests per minute per IP address
    
    Rationale:
    - ARRAY containment filter (WHERE tickers[] CONTAINS 'AAPL')
    - Uses GIN index on tickers column for fast lookups
    - Same cost as list endpoint
    
    Endpoint cost: 🟢 LOW (indexed array filter)
    """
    config = RATE_LIMITS["posts:ticker"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:ticker",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_trending(request: Request):
    """
    Rate limit: GET /posts/trending endpoint
    
    Limit: 50 requests per minute per IP address
    
    Rationale:
    - GROUP BY aggregation: scans entire table, groups by ticker
    - unnest() ARRAY operation: expensive (expands arrays into rows)
    - COUNT(*) for each group: additional computation
    - More expensive than simple list query → lower limit
    
    This is a heavier query, not something you call many times per minute.
    
    Endpoint cost: 🟡 MEDIUM (GROUP BY + aggregation)
    
    Query example:
        SELECT ticker, COUNT(*) as mentions
        FROM reddit_posts, unnest(tickers) as ticker
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT 10
    
    Cost: O(n) where n = total rows in reddit_posts
    """
    config = RATE_LIMITS["posts:trending"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:trending",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_sentiment(request: Request):
    """
    Rate limit: GET /posts/sentiment/{ticker} endpoint
    
    Limit: 50 requests per minute per IP address
    
    Rationale:
    - Multiple aggregate functions: AVG(), COUNT(), SUM()
    - Scans table for matching ticker
    - Three calculations per row
    - Similar cost to trending endpoint
    
    Endpoint cost: 🟡 MEDIUM (aggregations)
    
    Query example:
        SELECT AVG(sentiment_score), COUNT(*), SUM(score)
        FROM reddit_posts
        WHERE tickers[] CONTAINS 'AAPL'
    """
    config = RATE_LIMITS["posts:sentiment"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:sentiment",
        limit=config.requests,
        period_seconds=period_seconds
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS WITH RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/", response_model=PostListResponse)
async def get_posts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _rate_limit = Depends(rate_limit_posts_list)  # ← Rate limit check happens here
) -> PostListResponse:
    """
    Get paginated Reddit posts
    
    Rate limited: 100 requests per minute per IP
    
    How rate limiting works:
    1. FastAPI calls Depends(rate_limit_posts_list)
    2. rate_limit_posts_list(request) is invoked
    3. check_rate_limit() is awaited:
       - Extracts client IP from request
       - Gets Redis client from app.state
       - Increments "ratelimit:posts:list:{ip}" counter in Redis
       - If counter > 100: raises HTTPException(429)
       - If counter <= 100: returns rate limit info
    4. If no exception: endpoint logic runs normally
    5. If exception: FastAPI returns JSON error response
    
    The _rate_limit parameter:
    - Name starts with _ to indicate it's internal (not user-provided)
    - We don't use it in the function (just ensure it's checked)
    - FastAPI still calls Depends() and waits for result
    - If 429 is raised, endpoint code never runs
    """
    
    # Calculate offset
    skip = (page - 1) * page_size
    
    # Get total count
    count_result = await db.execute(select(func.count(RedditPost.id)))
    total = count_result.scalar() or 0
    
    # Get posts
    result = await db.execute(
        select(RedditPost)
        .order_by(desc(RedditPost.score))
        .offset(skip)
        .limit(page_size)
    )
    
    posts = result.scalars().all()
    
    return PostListResponse(
        total=total,
        page=page,
        page_size=page_size,
        posts=[
            {
                "id": post.id,
                "title": post.title,
                "tickers": post.tickers or [],
                "sentiment_score": post.sentiment_score or 0.0,
                "score": post.score or 0,
                "url": post.url,
                "created_at": post.created_at
            }
            for post in posts
        ]
    )
    

@router.get("/ticker/{ticker}", response_model=PostByTickerResponse)
async def get_posts_by_ticker(
    ticker: str, 
    db: AsyncSession = Depends(get_db), 
    limit: int = Query(20, ge=1, le=100),
    _rate_limit = Depends(rate_limit_posts_ticker)  # ← Rate limit check
) -> PostByTickerResponse:
    """
    Get posts mentioning specific ticker
    
    Rate limited: 100 requests per minute per IP
    """
    result = await db.execute(
        select(RedditPost)
        .where(RedditPost.tickers.contains([ticker.upper()]))
        .order_by(desc(RedditPost.score))
        .limit(limit)
    )
    
    posts = result.scalars().all()
    
    return PostByTickerResponse(
        ticker=ticker.upper(),
        count=len(posts),
        posts=[
            {
                "title": post.title,
                "sentiment_score": post.sentiment_score or 0.0,
                "score": post.score or 0,
                "url": post.url
            }
            for post in posts
        ]
    )
    

@router.get("/trending", response_model=TrendingResponse)
async def get_trending_tickers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    _rate_limit = Depends(rate_limit_posts_trending)  # ← Rate limit check
) -> TrendingResponse:
    """
    Get most mentioned tickers (aggregation - more expensive)
    
    Rate limited: 50 requests per minute per IP (lower than simple reads)
    
    This endpoint uses GROUP BY which requires scanning entire reddit_posts table.
    The GROUP BY + unnest() is more expensive than simple filtered reads.
    Therefore: 50/min instead of 100/min
    """
    query = text("""
        SELECT ticker, COUNT(*) as mentions
        FROM reddit_posts, unnest(tickers) as ticker
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {"limit": limit})
    
    trending = [{"ticker": row[0], "mentions": row[1]} for row in result]
    return TrendingResponse(trending=trending)


@router.get("/sentiment/{ticker}", response_model=TickerSentiment)
async def get_ticker_sentiment(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _rate_limit = Depends(rate_limit_posts_sentiment)  # ← Rate limit check
) -> TickerSentiment:
    """
    Get aggregated sentiment for a specific ticker
    
    Rate limited: 50 requests per minute per IP
    
    This endpoint performs multiple aggregations (AVG, COUNT, SUM).
    More expensive than simple reads, so lower limit.
    """
    result = await db.execute(
        select(
            func.avg(RedditPost.sentiment_score).label('avg_sentiment'),
            func.count(RedditPost.id).label('post_count'),
            func.sum(RedditPost.score).label('total_engagement')
        ).where(RedditPost.tickers.contains([ticker.upper()]))
    )
    
    row = result.first()
    
    if not row or row.post_count == 0:
        return TickerSentiment(
            ticker=ticker.upper(),
            sentiment="No data",
            avg_score=0.0,
            post_count=0,
            total_engagement=0
        )
    
    avg_sentiment = float(row.avg_sentiment) if row.avg_sentiment else 0.0
    
    # Determine sentiment label
    if avg_sentiment >= 0.05:
        label = "bullish"
    elif avg_sentiment <= -0.05:
        label = "bearish"
    else:
        label = "neutral"
    
    return TickerSentiment(
        ticker=ticker.upper(),
        sentiment=label,
        avg_score=round(avg_sentiment, 3),
        post_count=row.post_count,
        total_engagement=row.total_engagement or 0
    )

from fastapi import FastAPI, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api.routes import posts, stocks
from backend.config.settings import settings
from backend.cache.redis_client import get_redis, close_redis
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone
from backend.database.config import get_db
from backend.models.reddit import RedditPost
from redis.asyncio import Redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup: 
        - Initialize Redis cache connection (for data caching)
        - Initialize Redis client for rate limiting (same instance)
    
    Shutdown: 
        - Close Redis connections gracefully
    
    Why two Redis purposes?
    1. Data cache: Stock prices, sentiment scores, trending tickers (5-15min TTL)
    2. Rate limiting: Request counters per IP per endpoint (per-minute TTL)
    
    They share the same Redis Cloud connection for simplicity and efficiency.
    """
    
    # ── STARTUP ────────────────────────────────────────────────────────────
    
    # Initialize cache (for RedisCache operations in endpoints)
    cache = await get_redis()
    print("✅ Redis cache connection initialized")
    
    # Initialize separate client for rate limiting
    # (Can be same Redis instance, different purpose)
    redis_url = settings.redis_url
    
    try:
        redis_client = Redis.from_url(
            redis_url,
            encoding="utf8",
            decode_responses=True,
            ssl=True,  # Required for Redis Cloud (Mumbai)
            ssl_certfile=None,  # Use system SSL certificates
            ssl_keyfile=None,
        )
        
        # Test connection
        await redis_client.ping()
        print("✅ Redis rate limiter connection initialized")
        
        # Store in app state (accessible in endpoints via request.app.state)
        app.state.redis_client = redis_client
        app.state.rate_limiter_enabled = True
        
    except Exception as e:
        print(f"⚠️  Redis rate limiter connection failed: {e}")
        print("   Rate limiting will be unavailable (graceful degradation)")
        app.state.rate_limiter_enabled = False
        app.state.redis_client = None
    
    yield  # ← App runs here, handling requests
    
    # ── SHUTDOWN ───────────────────────────────────────────────────────────
    
    # Close rate limiter Redis connection
    if app.state.redis_client:
        await app.state.redis_client.close()
        print("✅ Redis rate limiter connection closed")
    
    # Close cache Redis connection
    await close_redis()
    print("✅ Redis cache connection closed")


app = FastAPI(
    title="Temporal Sentiment Trader API",
    version="1.0.0",
    description="Reddit sentiment-based stock prediction API with TFT ensemble models",
    lifespan=lifespan
)

# CORS - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with versioned API prefix
API_PREFIX = "/api/v1"
app.include_router(posts.router, prefix=API_PREFIX)
app.include_router(stocks.router, prefix=API_PREFIX)

@app.get("/")
async def root():
    return {"message": "Temporal Sentiment Trader API", "status": "running"}

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    include_stats: bool = Query(False, description="Include DB stats like total_posts")
):
    """Health check with database connectivity and rate limiter status"""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))

        # Test Redis rate limiter connectivity
        redis_status = "unavailable"
        if app.state.redis_client:
            try:
                await app.state.redis_client.ping()
                redis_status = "connected"
            except Exception:
                redis_status = "disconnected"

        payload = {
            "status": "healthy",
            "database": "connected",
            "rate_limiter": redis_status,
            "rate_limiting_enabled": app.state.rate_limiter_enabled,
            "environment": settings.environment,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if include_stats:
            # Lightweight stats path to avoid heavy counts by default
            result = await db.execute(select(func.count(RedditPost.id)))
            post_count = result.scalar() or 0
            payload["total_posts"] = post_count

        return payload
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "rate_limiter": "unknown",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

from fastapi import FastAPI, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import posts, stocks
from backend.config.settings import settings
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone
from backend.database.config import get_db
from backend.models.reddit import RedditPost


app = FastAPI(
    title="TFT Stock Trader API",
    version="1.0.0",
    description="Reddit sentiment-based stock prediction API"
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
    return {"message": "TFT Stock Trader API", "status": "running"}

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    include_stats: bool = Query(False, description="Include DB stats like total_posts")
):
    """Health check with database connectivity"""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))

        payload = {
            "status": "healthy",
            "database": "connected",
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
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

"""
Redis cache module for high-performance data caching.

This module provides async Redis operations for caching:
- Stock prices (5-minute TTL)
- Sentiment aggregates (15-minute TTL)
- Trending tickers (10-minute TTL)

Pattern: Write-Through with TTL (hybrid approach)
- Cache updated on every write
- Automatic expiration for staleness protection
- Fallback to DB on cache miss
"""
from backend.cache.redis_client import (
    RedisCache,
    get_redis,
    CacheKeys,
)

__all__ = ["RedisCache", "get_redis", "CacheKeys"]

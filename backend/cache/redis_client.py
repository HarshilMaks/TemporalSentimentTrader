"""
Async Redis client for caching layer.

IMPORTANT: Uses redis.asyncio for non-blocking operations.
Perplexity used sync redis.Redis() which BLOCKS the event loop!

Pattern: Write-Through with TTL
- Every DB write also updates cache
- TTL auto-expires stale data
- Cache miss falls back to DB

Why this pattern for swing trading:
1. Data freshness: 5-min delay acceptable for swing (not HFT)
2. Simplicity: No complex invalidation logic
3. Consistency: TTL guarantees eventual freshness
4. Performance: 1ms cache hit vs 50ms DB query
"""
import json
from typing import Any, Optional, List
from datetime import timedelta
import redis.asyncio as redis
from backend.config.settings import settings
from backend.utils.logger import logger


class CacheKeys:
    """
    Centralized cache key definitions.
    
    Pattern: {domain}:{entity}:{identifier}
    Examples:
        stock:price:AAPL
        stock:signals:TSLA
        sentiment:aggregate:GME
        trending:tickers:daily
    """
    
    @staticmethod
    def stock_price(ticker: str) -> str:
        """Latest price for a ticker"""
        return f"stock:price:{ticker.upper()}"
    
    @staticmethod
    def stock_signals(ticker: str) -> str:
        """Momentum signals for a ticker"""
        return f"stock:signals:{ticker.upper()}"
    
    @staticmethod
    def sentiment_aggregate(ticker: str) -> str:
        """Aggregate sentiment for a ticker"""
        return f"sentiment:aggregate:{ticker.upper()}"
    
    @staticmethod
    def trending_tickers() -> str:
        """Top trending tickers list"""
        return "trending:tickers:daily"
    
    @staticmethod
    def stock_history(ticker: str, days: int) -> str:
        """Historical prices cache"""
        return f"stock:history:{ticker.upper()}:{days}d"


class RedisCache:
    """
    Async Redis cache client.
    
    Usage:
        cache = RedisCache()
        await cache.connect()
        
        # Simple get/set
        await cache.set("key", {"data": "value"}, ttl=300)
        data = await cache.get("key")
        
        # Stock-specific helpers
        await cache.set_stock_price("AAPL", 150.25)
        price = await cache.get_stock_price("AAPL")
    """
    
    # TTL constants (in seconds)
    TTL_PRICE = 300           # 5 minutes - stock prices
    TTL_SIGNALS = 300         # 5 minutes - momentum signals
    TTL_SENTIMENT = 900       # 15 minutes - sentiment aggregates
    TTL_TRENDING = 600        # 10 minutes - trending list
    TTL_HISTORY = 1800        # 30 minutes - historical data (larger, less frequent)
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """
        Establish connection to Redis Cloud.
        
        Uses connection pooling for efficiency.
        """
        if self._connected:
            return
        
        try:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,  # Return strings, not bytes
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info("✅ Redis cache connected")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._connected = False
            # Don't raise - cache is optional, app should work without it
    
    async def disconnect(self) -> None:
        """Close Redis connection gracefully."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis cache disconnected")
    
    @property
    def is_connected(self) -> bool:
        """Check if cache is available."""
        return self._connected and self._client is not None
    
    # ─────────────────────────────────────────────────────────────────
    # Core Operations
    # ─────────────────────────────────────────────────────────────────
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Returns None on cache miss or if cache unavailable.
        Deserializes JSON automatically.
        """
        if not self.is_connected:
            return None
        
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Return raw string if not JSON
                return value
                
        except Exception as e:
            logger.warning(f"Cache GET error for {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 300
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Any JSON-serializable value
            ttl: Time-to-live in seconds (default 5 min)
        
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_connected:
            return False
        
        try:
            # Serialize to JSON
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)
            
            await self._client.setex(key, ttl, value)
            return True
            
        except Exception as e:
            logger.warning(f"Cache SET error for {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a specific cache key."""
        if not self.is_connected:
            return False
        
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache DELETE error for {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Example: delete_pattern("stock:*") removes all stock caches
        
        WARNING: KEYS command is O(N) - use sparingly!
        For production with millions of keys, use SCAN instead.
        """
        if not self.is_connected:
            return 0
        
        try:
            keys = await self._client.keys(pattern)
            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"Deleted {deleted} keys matching '{pattern}'")
                return deleted
            return 0
            
        except Exception as e:
            logger.warning(f"Cache DELETE PATTERN error for {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_connected:
            return False
        
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False
    
    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key (in seconds). Returns -1 if no TTL, -2 if not found."""
        if not self.is_connected:
            return -2
        
        try:
            return await self._client.ttl(key)
        except Exception:
            return -2
    
    # ─────────────────────────────────────────────────────────────────
    # Stock-Specific Helpers (Write-Through Pattern)
    # ─────────────────────────────────────────────────────────────────
    
    async def get_stock_price(self, ticker: str) -> Optional[float]:
        """Get cached stock price."""
        value = await self.get(CacheKeys.stock_price(ticker))
        return float(value) if value is not None else None
    
    async def set_stock_price(self, ticker: str, price: float) -> bool:
        """Cache stock price with 5-min TTL."""
        return await self.set(
            CacheKeys.stock_price(ticker),
            price,
            ttl=self.TTL_PRICE
        )
    
    async def get_stock_signals(self, ticker: str) -> Optional[dict]:
        """Get cached momentum signals."""
        return await self.get(CacheKeys.stock_signals(ticker))
    
    async def set_stock_signals(self, ticker: str, signals: dict) -> bool:
        """Cache momentum signals with 5-min TTL."""
        return await self.set(
            CacheKeys.stock_signals(ticker),
            signals,
            ttl=self.TTL_SIGNALS
        )
    
    async def get_sentiment(self, ticker: str) -> Optional[dict]:
        """Get cached sentiment aggregate."""
        return await self.get(CacheKeys.sentiment_aggregate(ticker))
    
    async def set_sentiment(self, ticker: str, sentiment: dict) -> bool:
        """Cache sentiment with 15-min TTL."""
        return await self.set(
            CacheKeys.sentiment_aggregate(ticker),
            sentiment,
            ttl=self.TTL_SENTIMENT
        )
    
    async def get_trending(self) -> Optional[List[dict]]:
        """Get cached trending tickers list."""
        return await self.get(CacheKeys.trending_tickers())
    
    async def set_trending(self, tickers: List[dict]) -> bool:
        """Cache trending list with 10-min TTL."""
        return await self.set(
            CacheKeys.trending_tickers(),
            tickers,
            ttl=self.TTL_TRENDING
        )
    
    # ─────────────────────────────────────────────────────────────────
    # Cache Stats (for monitoring)
    # ─────────────────────────────────────────────────────────────────
    
    async def get_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        if not self.is_connected:
            return {"status": "disconnected"}
        
        try:
            info = await self._client.info("stats")
            memory = await self._client.info("memory")
            
            return {
                "status": "connected",
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0) / 
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1) * 100,
                    2
                ),
                "memory_used_mb": round(memory.get("used_memory", 0) / 1024 / 1024, 2),
                "memory_peak_mb": round(memory.get("used_memory_peak", 0) / 1024 / 1024, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# Singleton instance and FastAPI dependency
# ─────────────────────────────────────────────────────────────────────

_redis_cache: Optional[RedisCache] = None


async def get_redis() -> RedisCache:
    """
    FastAPI dependency for Redis cache.
    
    Usage in endpoints:
        @router.get("/price/{ticker}")
        async def get_price(
            ticker: str,
            cache: RedisCache = Depends(get_redis)
        ):
            cached = await cache.get_stock_price(ticker)
            if cached:
                return {"price": cached, "source": "cache"}
            ...
    """
    global _redis_cache
    
    if _redis_cache is None:
        _redis_cache = RedisCache()
        await _redis_cache.connect()
    
    return _redis_cache


async def close_redis() -> None:
    """Close Redis connection on app shutdown."""
    global _redis_cache
    
    if _redis_cache is not None:
        await _redis_cache.disconnect()
        _redis_cache = None

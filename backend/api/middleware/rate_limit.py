"""
Rate Limiting Middleware and Dependencies

Purpose: Implement distributed rate limiting using Redis backend.
This ensures rate limits work correctly in multi-instance deployments.

Why Redis-backed instead of in-memory (like slowapi default):
- In-memory: Works on single server only, fails when scaling to multiple instances
- Redis-backed: Shared state across ALL API instances automatically
- Production-ready: Essential for containerized/cloud deployments

How it works:
1. Request comes in → Extract client IP
2. Create Redis key: "ratelimit:{endpoint_key}:{ip}"
3. Increment counter atomically (INCR)
4. Check if counter > limit
5. Set TTL on key to period duration
6. Return 429 if exceeded
"""

from fastapi import Request, HTTPException, status, Depends
from redis.asyncio import Redis
from backend.utils.logger import logger
from backend.config.rate_limits import RATE_LIMITS, get_period_seconds
from typing import Optional


class RedisRateLimiter:
    """
    Distributed Rate Limiter using Redis as backend.
    
    Architecture:
    
    ┌─────────────┐
    │ API Request │ (from client IP: 203.0.113.45)
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────────────────────┐
    │ Extract endpoint key + IP address   │
    │ e.g., "posts:list" + "203.0.113.45" │
    └──────┬──────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────┐
    │ Create Redis key:                   │
    │ "ratelimit:posts:list:203.0.113.45" │
    └──────┬──────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ INCR key (atomic operation)              │
    │ First time: set to 1, then set TTL=60s   │
    │ Other times: just increment              │
    └──────┬───────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ Check if counter > limit (100)           │
    │ If yes: return 429 Too Many Requests     │
    │ If no: allow request, return info        │
    └──────────────────────────────────────────┘
    
    Key Design Decisions:
    - INCR is atomic: No race conditions with multiple threads/processes
    - TTL auto-expires keys: No cleanup needed, Redis handles it
    - Fail-open on error: If Redis unavailable, allow request (better UX)
    """
    
    def __init__(self, redis_client: Redis):
        """
        Initialize with Redis client
        
        Args:
            redis_client: Connected redis.asyncio.Redis instance
                         Already connected to Redis Cloud with proper SSL
        """
        self.redis = redis_client
    
    async def is_rate_limited(
        self,
        key: str,
        ip_address: str,
        limit: int,
        period_seconds: int
    ) -> tuple[bool, dict]:
        """
        Check if request exceeds rate limit.
        
        Main logic for rate limiting - handles Redis operations.
        
        Args:
            key (str): Endpoint identifier (e.g., "posts:list")
            ip_address (str): Client IP address (e.g., "203.0.113.45")
            limit (int): Maximum requests allowed (e.g., 100)
            period_seconds (int): Time window in seconds (60=1min, 3600=1hour)
        
        Returns:
            tuple[bool, dict]:
                - bool: True if request should be REJECTED (limited)
                - dict: Rate limit info with keys:
                    * limit: Original limit
                    * current: Current counter value
                    * remaining: Remaining requests
                    * reset_in_seconds: TTL (when counter resets)
        
        Implementation Details:
        
        Step 1: Create unique key for this IP + endpoint
            Key format: "ratelimit:{endpoint}:{ip}"
            Example: "ratelimit:posts:list:203.0.113.45"
            This ensures each IP has separate count per endpoint
        
        Step 2: INCR (increment) counter atomically
            redis-py: await self.redis.incr(redis_key)
            - If key doesn't exist: creates it with value 1
            - If key exists: increments by 1
            - Atomic: No race conditions!
        
        Step 3: Set TTL on first request
            - If INCR returned 1 (first request): set expiration
            - redis-py: await self.redis.expire(redis_key, period_seconds)
            - After period_seconds: Redis automatically deletes the key
            - Next request after expiry: counter resets to 1
        
        Step 4: Get remaining time to reset (TTL)
            - redis-py: await self.redis.ttl(redis_key)
            - Returns: seconds until key expires (-1 if no TTL, -2 if not found)
            - Used for X-RateLimit-Reset-In header
        
        Step 5: Check if limit exceeded
            - is_limited = current_count > limit
            - If counter reaches 101 and limit is 100: LIMIT EXCEEDED
            - Return 429 to client
        
        Step 6: Prepare response info
            - limit: What we told client (100)
            - current: What they actually hit (101)
            - remaining: max(0, 100 - 101) = 0
            - reset_in_seconds: Time until counter resets
        """
        
        # ── STEP 1: Create unique Redis key ──────────────────────────────────
        redis_key = f"ratelimit:{key}:{ip_address}"
        
        try:
            # ── STEP 2: Increment counter atomically ─────────────────────────
            # This is THE key operation for rate limiting
            # INCR is atomic: guaranteed no race conditions
            current_count = await self.redis.incr(redis_key)
            
            # ── STEP 3: Set TTL on first request ────────────────────────────
            # When INCR returns 1, this is the very first request in this period
            # We need to set an expiration time so the counter resets
            if current_count == 1:
                # Set TTL = period (e.g., 60 seconds for "per minute" limit)
                # When TTL expires, Redis deletes the key automatically
                # Next request: INCR creates key at 1 again (counter resets)
                await self.redis.expire(redis_key, period_seconds)
            
            # ── STEP 4: Get TTL (time to reset) ────────────────────────────
            # This tells us how many seconds until the counter resets
            # Example: If limit is 100/minute and you make 50 requests:
            #   - TTL might be 45 seconds remaining
            #   - You can make 50 more requests in next 45 seconds
            ttl = await self.redis.ttl(redis_key)
            
            # ── STEP 5: Check if limit exceeded ───────────────────────────
            # Simple comparison: is actual > allowed?
            is_limited = current_count > limit
            
            # ── STEP 6: Prepare response info ─────────────────────────────
            info = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_in_seconds": ttl if ttl > 0 else 0
            }
            
            # Log for monitoring
            logger.debug(
                f"RateLimit check - Endpoint: {key}, IP: {ip_address}, "
                f"Requests: {current_count}/{limit}, Remaining: {info['remaining']}"
            )
            
            return is_limited, info
            
        except Exception as e:
            # ── ERROR HANDLING: Graceful degradation ────────────────────────
            # If Redis is down/unavailable:
            # - Don't block users (fail-open policy)
            # - Log the error for debugging
            # - Continue without rate limiting
            # - Better to have no limit than to break the entire API
            logger.error(f"Rate limiter error for {key} from {ip_address}: {e}")
            logger.warning("Rate limiting disabled - Redis unavailable")
            
            # Return "not limited" so request proceeds
            return False, {"error": "rate_limiter_unavailable"}


async def check_rate_limit(
    request: Request,
    endpoint_key: str,
    limit: int,
    period_seconds: int
) -> dict:
    """
    Dependency function to check rate limit.
    
    This is a FastAPI dependency - used in endpoint function parameters.
    FastAPI automatically injects this, checks rate limit, and either:
    - Raises HTTPException (429) if limited
    - Returns rate_limit_info if allowed
    
    Key advantage: Transparent to endpoint logic
    Endpoint author just adds "_rate_limit = Depends(check_rate_limit(...))"
    Automatic checking happens before endpoint code runs.
    
    Args:
        request (Request): FastAPI Request object (contains headers, client IP, etc.)
        endpoint_key (str): Endpoint identifier (e.g., "posts:list")
        limit (int): Maximum requests allowed (e.g., 100)
        period_seconds (int): Time window in seconds (e.g., 60 for 1 minute)
    
    Returns:
        dict: Rate limit info with limit/current/remaining/reset_in_seconds
    
    Raises:
        HTTPException: 429 Too Many Requests if limited
    
    HTTP 429 Response Structure:
    {
        "detail": {
            "error": "rate_limit_exceeded",
            "message": "Exceeded 100 requests per 60s",
            "limit": 100,
            "remaining": 0,
            "reset_in_seconds": 45
        }
    }
    
    Usage in endpoint:
    
        @router.get("/posts/")
        async def list_posts(
            db: AsyncSession = Depends(get_db),
            _rate_limit = Depends(
                lambda req: check_rate_limit(
                    req, "posts:list", 100, 60
                )
            )
        ):
            # If we reach here: rate limit was checked and passed!
            # If rate limited: 429 raised automatically
            return get_posts_logic(db)
    
    Alternative - using helpers:
    
        async def limit_posts(req: Request):
            config = RATE_LIMITS["posts:list"]
            period_sec = get_period_seconds(config.period)
            return await check_rate_limit(
                req, "posts:list", config.requests, period_sec
            )
        
        @router.get("/posts/")
        async def list_posts(
            db: AsyncSession = Depends(get_db),
            _rate_limit = Depends(limit_posts)
        ):
            pass
    """
    
    # ── Get client IP address ──────────────────────────────────────────────
    # Request has .client attribute with IP + port
    # Example: "203.0.113.45"
    client_ip = request.client.host if request.client else "unknown"
    
    # ── Get Redis client from app state ────────────────────────────────────
    # We stored it in app.state during startup (in main.py lifespan)
    # This is the same Redis Cloud instance used for data caching
    redis_client = request.app.state.redis_client
    
    # ── Create limiter instance ────────────────────────────────────────────
    # RedisRateLimiter handles all Redis operations
    limiter = RedisRateLimiter(redis_client)
    
    # ── Check if rate limited ────────────────────────────────────────────────
    # this is the main check
    is_limited, info = await limiter.is_rate_limited(
        key=endpoint_key,
        ip_address=client_ip,
        limit=limit,
        period_seconds=period_seconds
    )
    
    # ── Return 429 if limited ────────────────────────────────────────────────
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Exceeded {limit} requests per {period_seconds}s",
                "limit": info["limit"],
                "current": info.get("current", 0),
                "remaining": info["remaining"],
                "reset_in_seconds": info["reset_in_seconds"]
            }
        )
    
    # ── Return rate limit info for response headers ──────────────────────────
    # Caller can use this to add X-RateLimit-* headers to response
    return info

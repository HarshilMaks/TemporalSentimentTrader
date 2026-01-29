"""
Test Celery and Redis Cloud connectivity.

Run this after configuring Redis Cloud URL in .env:
    python scripts/test_celery.py
"""
import asyncio
from backend.celery_app import app
from backend.tasks.scraping_tasks import fetch_single_stock
from backend.utils.logger import logger


def test_redis_connection():
    """Test Redis Cloud connection via Celery."""
    try:
        # Inspect Celery broker connection
        inspector = app.control.inspect()
        
        # This will fail if Redis is not accessible
        stats = inspector.stats()
        
        if stats:
            logger.info("✅ Redis Cloud connection successful!")
            logger.info(f"Active workers: {list(stats.keys())}")
            return True
        else:
            logger.warning("⚠️ No Celery workers running")
            logger.info("Start a worker with: make worker")
            return True  # Redis is accessible, just no workers yet
            
    except Exception as e:
        logger.error(f"❌ Redis Cloud connection failed: {e}")
        logger.info("\nMake sure:")
        logger.info("1. Redis Cloud URL is set in .env file")
        logger.info("2. Format: redis://default:<password>@<host>:<port>")
        logger.info("3. Redis Insight shows 'Connected' status")
        return False


def test_task_delay():
    """Test task queueing (requires worker to be running)."""
    try:
        logger.info("\n📤 Queuing a test task...")
        result = fetch_single_stock.delay("AAPL", "1d")
        logger.info(f"Task queued with ID: {result.id}")
        logger.info("Check task status with: result.status")
        logger.info("\nNote: Task will only execute if a worker is running!")
        logger.info("Start worker in another terminal: make worker")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to queue task: {e}")
        return None


if __name__ == "__main__":
    logger.info("=== Celery + Redis Cloud Connection Test ===\n")
    
    # Test 1: Redis connection
    if test_redis_connection():
        logger.info("\n✅ Test 1 passed: Redis Cloud is accessible\n")
        
        # Test 2: Task queueing
        result = test_task_delay()
        
        if result:
            logger.info("\n✅ Test 2 passed: Task queued successfully")
            logger.info(f"\nTask ID: {result.id}")
            logger.info("Task will execute once worker is started!")
        else:
            logger.error("\n❌ Test 2 failed: Could not queue task")
    else:
        logger.error("\n❌ Test 1 failed: Cannot connect to Redis Cloud")
        logger.info("\nNext steps:")
        logger.info("1. Check your .env file for REDIS_URL")
        logger.info("2. Verify Redis Cloud credentials in Redis Insight")
        logger.info("3. Ensure Redis Cloud instance is active")

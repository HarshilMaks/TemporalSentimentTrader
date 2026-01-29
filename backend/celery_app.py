"""
Celery application for background tasks.

This module initializes Celery with Redis Cloud as the broker/backend.
Tasks include:
- Scheduled stock data fetching
- Scheduled Reddit scraping
- ML model training
- Signal monitoring
"""
from celery import Celery
from celery.schedules import crontab
from backend.config.settings import settings

# Initialize Celery app
app = Celery(
    "tft_trader",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "backend.tasks.scraping_tasks",
        "backend.tasks.ml_tasks",
        "backend.tasks.maintenance_tasks",
    ]
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        "backend.tasks.scraping_tasks.*": {"queue": "scraping"},
        "backend.tasks.ml_tasks.*": {"queue": "ml"},
    },
)

# Scheduled tasks (Beat schedule)
app.conf.beat_schedule = {
    # Scrape Reddit every 30 minutes during market hours
    "scrape-reddit-posts": {
        "task": "backend.tasks.scraping_tasks.scrape_reddit_scheduled",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
        "options": {"queue": "scraping"},
    },
    
    # Fetch stock data every hour during market hours
    "fetch-stock-data": {
        "task": "backend.tasks.scraping_tasks.fetch_stocks_scheduled",
        "schedule": crontab(minute=0, hour="*/1"),  # Every hour
        "options": {"queue": "scraping"},
    },
    
    # Generate trading signals daily at market open (9:30 AM EST = 2:30 PM UTC)
    "generate-signals": {
        "task": "backend.tasks.ml_tasks.generate_daily_signals",
        "schedule": crontab(hour=14, minute=30),  # 2:30 PM UTC
        "options": {"queue": "ml"},
    },
    
    # Monitor active signals every 5 minutes during market hours
    "monitor-signals": {
        "task": "backend.tasks.ml_tasks.monitor_active_signals",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {"queue": "ml"},
    },
    
    # ─────────────────────────────────────────────────────────────────
    # Maintenance Tasks
    # ─────────────────────────────────────────────────────────────────
    
    # Clean up old data weekly (Sunday 3 AM UTC)
    "cleanup-old-data": {
        "task": "backend.tasks.maintenance_tasks.cleanup_old_data",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
        "options": {"queue": "scraping"},
    },
    
    # Generate system report daily (6 AM UTC)
    "system-report": {
        "task": "backend.tasks.maintenance_tasks.generate_system_report",
        "schedule": crontab(hour=6, minute=0),  # Daily 6 AM
        "options": {"queue": "scraping"},
    },
    
    # Refresh trending cache every 10 minutes
    "refresh-trending-cache": {
        "task": "backend.tasks.maintenance_tasks.refresh_trending_cache",
        "schedule": crontab(minute="*/10"),  # Every 10 min
        "options": {"queue": "scraping"},
    },
}

if __name__ == "__main__":
    app.start()

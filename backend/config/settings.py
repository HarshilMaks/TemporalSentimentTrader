from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables (.env file)"""
    
    # Database - REQUIRED: Set DATABASE_URL in .env file
    # For Neon DB: postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
    database_url: str
    
    # Security - Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    secret_key: str = "dev-secret-key-change-in-production"
    
    # Redis (optional for caching)
    redis_url: str = "redis://localhost:6379/0"
    
    # Environment
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # JWT Configuration
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # API Configuration
    api_v1_prefix: str = "/api/v1"
    
    # CORS Configuration
    cors_origins: list[str] = ["http://localhost:3000"]
    
    @property
    def async_database_url(self) -> str:
        """Convert sync postgres URL to async asyncpg URL for Neon DB
        
        asyncpg doesn't support sslmode/channel_binding query params,
        so we need to remove them and handle SSL via connect_args instead
        """
        url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        # Remove sslmode and channel_binding params (incompatible with asyncpg)
        url = url.split("?")[0]
        return url
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance - loads once from .env"""
    return Settings()


settings = get_settings()

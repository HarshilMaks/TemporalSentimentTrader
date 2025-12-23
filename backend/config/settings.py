from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # API Configuration
    api_v1_prefix: str = "/api/v1"
    
    # CORS Configuration
    cors_origins: list = ["http://localhost:3000"]
    
    @property
    def async_database_url(self) -> str:
        """Convert sync postgres URL to async asyncpg URL"""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings():
    """Cached settings instance"""
    return Settings()


settings = get_settings()

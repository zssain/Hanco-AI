"""
Core configuration for Hanco-AI Backend
Environment variables, settings, constants
"""
from functools import lru_cache
from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses lru_cache for singleton pattern.
    """
    
    # ==================== App Settings ====================
    PROJECT_NAME: str = "Hanco AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # ==================== API Settings ====================
    API_V1_PREFIX: str = "/api/v1"
    
    # ==================== Firebase Configuration ====================
    # REQUIRED: Set GOOGLE_APPLICATION_CREDENTIALS (path to JSON) or FIREBASE_CREDENTIALS_JSON (inline JSON string)
    FIREBASE_PROJECT_ID: str = Field(default="", env="FIREBASE_PROJECT_ID")
    
    # Firebase Web Config (for frontend reference) - MUST be set via environment variables
    FIREBASE_API_KEY: str = Field(default="", env="FIREBASE_API_KEY")
    FIREBASE_AUTH_DOMAIN: str = Field(default="", env="FIREBASE_AUTH_DOMAIN")
    FIREBASE_STORAGE_BUCKET: str = Field(default="", env="FIREBASE_STORAGE_BUCKET")
    FIREBASE_MESSAGING_SENDER_ID: str = Field(default="", env="FIREBASE_MESSAGING_SENDER_ID")
    FIREBASE_APP_ID: str = Field(default="", env="FIREBASE_APP_ID")
    FIREBASE_MEASUREMENT_ID: str = Field(default="", env="FIREBASE_MEASUREMENT_ID")
    
    # ==================== AI Services ====================
    # REQUIRED: Set via environment variable
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")  # Optional fallback
    
    # ==================== Weather Service ====================
    OPEN_METEO_URL: str = Field(default="https://api.open-meteo.com/v1/forecast", env="OPEN_METEO_URL")
    
    # ==================== ML Model ====================
    ONNX_MODEL_PATH: str = Field(default="./ml/models/model.onnx", env="ONNX_MODEL_PATH")
    
    # ==================== Frontend & CORS ====================
    FRONTEND_URL: str = Field(default="http://localhost:5173", env="FRONTEND_URL")
    # ALLOWED_ORIGINS can be set as comma-separated list in environment
    # Example: ALLOWED_ORIGINS="http://localhost:5173,https://yourdomain.com"
    ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080", "http://51.21.130.26"],
        env="ALLOWED_ORIGINS"
    )
    
    # ==================== Crawl4AI Settings ====================
    SCRAPING_ENABLED: bool = Field(default=True, env="SCRAPING_ENABLED")
    SCRAPING_INTERVAL_HOURS: int = Field(default=24, env="SCRAPING_INTERVAL_HOURS")
    COMPETITOR_SCRAPE_CONCURRENCY: int = Field(default=4, env="COMPETITOR_SCRAPE_CONCURRENCY")
    
    # ==================== Logging ====================
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # ==================== Rate Limiting ====================
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    RATE_LIMIT_AI_PER_MINUTE: int = Field(default=10, env="RATE_LIMIT_AI_PER_MINUTE")
    
    # ==================== Security ====================
    MAX_REQUEST_SIZE_MB: int = Field(default=10, env="MAX_REQUEST_SIZE_MB")
    ENABLE_PAYMENT_SIMULATOR: bool = Field(default=False, env="ENABLE_PAYMENT_SIMULATOR")
    AI_MAX_INPUT_LENGTH: int = Field(default=2000, env="AI_MAX_INPUT_LENGTH")
    AI_MAX_TOKEN_BUDGET: int = Field(default=4000, env="AI_MAX_TOKEN_BUDGET")
    CRON_SECRET: str = Field(default="", env="CRON_SECRET")  # Required for cron/admin endpoints
    
    # ==================== Pricing Cache ====================
    PRICING_CACHE_ENABLED: bool = Field(default=True, env="PRICING_CACHE_ENABLED")
    PRICING_CACHE_TTL_MINUTES: int = Field(default=30, env="PRICING_CACHE_TTL_MINUTES")
    
    @field_validator('ALLOWED_ORIGINS', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from CSV string, JSON array string, or list"""
        if isinstance(v, str):
            # Try to parse as JSON array first
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Fall back to comma-separated string
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        if isinstance(v, list):
            return v
        return [str(v)]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields in .env file (like GOOGLE_APPLICATION_CREDENTIALS)


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached Settings instance (singleton pattern).
    Uses lru_cache to ensure only one instance is created.
    """
    return Settings()


# Global settings instance
settings = get_settings()

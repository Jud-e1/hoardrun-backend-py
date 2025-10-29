"""
Application configuration using Pydantic BaseSettings for environment-based configuration.
"""
from typing import List, Optional
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="Fintech Backend API", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "https://hoardruns.vercel.app", "https://hoardrun.vercel.app"], 
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_allow_methods: List[str] = Field(default=["*"], description="Allowed CORS methods")
    cors_allow_headers: List[str] = Field(default=["*"], description="Allowed CORS headers")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # External service configurations
    payment_gateway_url: str = Field(
        default="https://mock-payment-gateway.com", 
        description="Payment gateway API URL"
    )
    payment_gateway_timeout: int = Field(default=30, description="Payment gateway timeout in seconds")
    
    bank_api_url: str = Field(
        default="https://mock-bank-api.com", 
        description="Bank API URL"
    )
    bank_api_timeout: int = Field(default=30, description="Bank API timeout in seconds")
    
    market_data_url: str = Field(
        default="https://mock-market-data.com", 
        description="Market data provider URL"
    )
    market_data_timeout: int = Field(default=15, description="Market data timeout in seconds")
    
    mobile_money_url: str = Field(
        default="https://mock-mobile-money.com", 
        description="Mobile money service URL"
    )
    mobile_money_timeout: int = Field(default=30, description="Mobile money timeout in seconds")
    
    # Mastercard API Configuration
    mastercard_api_key: str = Field(
        default="", 
        description="Mastercard API key"
    )
    mastercard_partner_id: str = Field(
        default="", 
        description="Mastercard Partner ID"
    )
    mastercard_environment: str = Field(
        default="sandbox", 
        description="Mastercard environment (sandbox/production)"
    )
    mastercard_cert_path: str = Field(
        default="/secure/certs/mastercard/hoardrun.p12", 
        description="Path to Mastercard certificate file"
    )
    mastercard_private_key_path: str = Field(
        default="/secure/certs/mastercard/hoardrun.key", 
        description="Path to Mastercard private key file"
    )
    mastercard_client_id: str = Field(
        default="", 
        description="Mastercard Client ID"
    )
    mastercard_org_name: str = Field(
        default="Hoardrun", 
        description="Mastercard Organization Name"
    )
    mastercard_country: str = Field(
        default="GH", 
        description="Mastercard Country Code"
    )
    mastercard_cert_password: str = Field(
        default="", 
        description="Mastercard Certificate Password"
    )
    mastercard_timeout: int = Field(default=30, description="Mastercard API timeout in seconds")
    
    # MTN MOMO API Configuration
    momo_api_url: str = Field(
        default="https://sandbox.momodeveloper.mtn.com", 
        description="MTN MOMO API URL"
    )
    momo_primary_key: str = Field(
        default="", 
        description="MTN MOMO Primary Key"
    )
    momo_secondary_key: str = Field(
        default="", 
        description="MTN MOMO Secondary Key"
    )
    momo_target_environment: str = Field(
        default="sandbox", 
        description="MTN MOMO Target Environment"
    )
    momo_timeout: int = Field(default=30, description="MTN MOMO API timeout in seconds")

    # Paystack API Configuration
    paystack_public_key: str = Field(
        default="",
        description="Paystack Public Key"
    )
    paystack_secret_key: str = Field(
        default="",
        description="Paystack Secret Key"
    )
    paystack_environment: str = Field(
        default="test",
        description="Paystack environment (test/live)"
    )
    paystack_webhook_secret: str = Field(
        default="",
        description="Paystack Webhook Secret"
    )
    paystack_timeout: int = Field(default=30, description="Paystack API timeout in seconds")

    # Java Security Integration
    java_security_enabled: bool = Field(
        default=False,
        description="Enable integration with Java security services"
    )
    java_gateway_url: str = Field(
        default="http://localhost:8080",
        description="Java API Gateway URL"
    )
    java_auth_service_url: str = Field(
        default="http://localhost:8081",
        description="Java Auth Service URL"
    )
    java_transaction_service_url: str = Field(
        default="http://localhost:8082",
        description="Java Transaction Service URL"
    )
    java_audit_service_url: str = Field(
        default="http://localhost:8083",
        description="Java Audit Service URL"
    )
    java_jwt_secret: str = Field(
        default="c2VjdXJlLXN1cGVyLXNlY3JldC1kZW1vLXNob3VsZC1iZS0zMi1ieXRlcy1vci1sb25nZXI=",
        description="Java JWT secret (base64 encoded)"
    )

    # Rate limiting settings
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
    
    # Cache settings
    cache_ttl: int = Field(default=300, description="Default cache TTL in seconds")
    exchange_rate_cache_ttl: int = Field(default=3600, description="Exchange rate cache TTL in seconds")
    market_data_cache_ttl: int = Field(default=60, description="Market data cache TTL in seconds")
    
    # Business settings
    default_currency: str = Field(default="USD", description="Default currency code")
    supported_currencies: List[str] = Field(
        default=["USD", "EUR", "GBP", "KES", "UGX", "TZS"], 
        description="Supported currency codes"
    )
    max_transfer_amount: float = Field(default=100000.0, description="Maximum transfer amount")
    min_transfer_amount: float = Field(default=1.0, description="Minimum transfer amount")
    
    # Security settings
    request_timeout: int = Field(default=30, description="Default request timeout in seconds")
    max_request_size: int = Field(default=1048576, description="Maximum request size in bytes (1MB)")
    
    # Database settings
    database_url: str = Field(
        default="postgresql://hoardrun_srcm_user:DD5GKZbGUUb7jP3Oem6cTnQMBZOchKKx@dpg-d3svuqgdl3ps73avqgeg-a.oregon-postgres.render.com/hoardrun_srcm",
        description="Database connection URL"
    )
    database_pool_size: int = Field(
        default=20,
        description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=30,
        description="Database connection pool max overflow"
    )
    database_pool_timeout: int = Field(
        default=30,
        description="Database connection pool timeout in seconds"
    )
    database_pool_recycle: int = Field(
        default=3600,
        description="Database connection pool recycle time in seconds"
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        description="Enable database connection pool pre-ping"
    )
    database_echo: bool = Field(
        default=False,
        description="Enable SQLAlchemy query logging"
    )
    database_ssl_mode: str = Field(
        default="prefer",
        description="PostgreSQL SSL mode (disable, allow, prefer, require, verify-ca, verify-full)"
    )
    database_connect_timeout: int = Field(
        default=10,
        description="Database connection timeout in seconds"
    )
    
    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0", 
        description="Redis connection URL"
    )
    
    # Security settings (JWT)
    secret_key: str = Field(
        default="your-secret-key-here", 
        description="Secret key for JWT token generation"
    )
    jwt_secret_key: str = Field(
        default="your-secret-key-here", 
        description="JWT secret key for token generation"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, 
        description="Access token expiration time in minutes"
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30, 
        description="JWT access token expiration time in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, 
        description="JWT refresh token expiration time in days"
    )
    
    # API settings
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 prefix")
    docs_url: str = Field(default="/docs", description="Swagger docs URL")
    redoc_url: str = Field(default="/redoc", description="ReDoc URL")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the allowed values."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()
    
    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format is one of the allowed values."""
        allowed_formats = ["json", "text"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Log format must be one of: {allowed_formats}")
        return v.lower()
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment is one of the allowed values."""
        allowed_envs = ["development", "staging", "production"]
        if v.lower() not in allowed_envs:
            raise ValueError(f"Environment must be one of: {allowed_envs}")
        return v.lower()
    
    @field_validator("default_currency")
    @classmethod
    def validate_default_currency(cls, v):
        """Validate default currency is a 3-letter code."""
        if len(v) != 3 or not v.isalpha():
            raise ValueError("Currency code must be a 3-letter alphabetic code")
        return v.upper()
    
    @field_validator("supported_currencies")
    @classmethod
    def validate_supported_currencies(cls, v):
        """Validate all supported currencies are 3-letter codes."""
        for currency in v:
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError(f"Currency code '{currency}' must be a 3-letter alphabetic code")
        return [currency.upper() for currency in v]
    
    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v):
        """Validate CORS origins format."""
        if "*" in v and len(v) > 1:
            raise ValueError("CORS origins cannot contain '*' with other origins")
        return v
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="",
    )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment variables."""
    global settings
    settings = Settings()
    return settings

"""
Configuration module for ECTHR Translator.
Manages settings for HUDOC, CURIA, and IATE database integrations.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = "ECTHR Translator"
    debug: bool = False

    # HUDOC (European Court of Human Rights)
    hudoc_base_url: str = "https://hudoc.echr.coe.int"
    hudoc_enabled: bool = True
    hudoc_max_retries: int = 3
    hudoc_timeout_seconds: int = 30
    hudoc_use_mock: bool = False  # Set to True to use mock data instead of real API

    # CURIA (Court of Justice of the European Union) via EUR-Lex
    eurlex_sparql_endpoint: str = "https://publications.europa.eu/webapi/rdf/sparql"
    curia_enabled: bool = True
    curia_max_retries: int = 3
    curia_timeout_seconds: int = 30
    curia_use_mock: bool = False  # Set to True to use mock data instead of real API

    # IATE (Interactive Terminology for Europe)
    iate_api_url: str = "https://iate.europa.eu/api"
    iate_enabled: bool = True
    iate_username: Optional[str] = None  # Set via IATE_USERNAME env var
    iate_api_key: Optional[str] = None   # Set via IATE_API_KEY env var
    iate_max_retries: int = 3
    iate_timeout_seconds: int = 30
    iate_use_mock: bool = True  # Default to mock until API keys are obtained

    # General API settings
    max_concurrent_requests: int = 5
    cache_ttl_seconds: int = 3600  # 1 hour

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

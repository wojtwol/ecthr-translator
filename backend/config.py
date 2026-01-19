"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str

    # Paths
    tm_path: Path = Path("/tmp/data/tm")
    upload_path: Path = Path("/tmp/data/uploads")
    output_path: Path = Path("/tmp/data/outputs")

    # Database
    database_url: str = "sqlite:////tmp/data/ecthr.db"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"

    # External Services
    hudoc_base_url: str = "https://hudoc.echr.coe.int"
    curia_base_url: str = "https://curia.europa.eu"
    hudoc_enabled: bool = True
    curia_enabled: bool = True

    # Citation Detection (Phase 1: detection only, no fetching)
    enable_citation_detection: bool = False  # Set to True to enable

    # TM Configuration
    tm_fuzzy_threshold: float = 0.75
    tm_max_results: int = 10
    max_tmx_size_mb: int = 500  # Larger limit for TM files

    # Translation Configuration
    max_file_size_mb: int = 50
    allowed_extensions: str = ".docx"
    default_language_pair: str = "EN-PL"

    # Retry Configuration
    hudoc_max_retries: int = 3
    hudoc_timeout_seconds: int = 30
    curia_max_retries: int = 3
    curia_timeout_seconds: int = 30
    claude_max_retries: int = 5
    claude_timeout_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.tm_path.mkdir(parents=True, exist_ok=True)
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

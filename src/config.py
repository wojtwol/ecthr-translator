"""
Configuration management for ECTHR Translator.

This module handles loading and validating configuration from environment
variables and configuration files with comprehensive error handling.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

from .exceptions import (
    ConfigurationError,
    MissingAPIKeyError,
    InvalidConfigurationError,
)

logger = logging.getLogger(__name__)


@dataclass
class TranslationConfig:
    """Configuration for the translation service."""
    api_key: str
    api_url: str = "https://api.translation-service.example.com/v1"
    timeout: float = 30.0
    max_retries: int = 3
    verify_ssl: bool = True


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None


@dataclass
class AppConfig:
    """Main application configuration."""
    translation: TranslationConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    default_source_language: Optional[str] = None
    default_target_language: str = "en"
    output_directory: str = "./output"


class ConfigLoader:
    """Loads and validates configuration from various sources.

    Configuration is loaded with the following priority (highest to lowest):
    1. Environment variables
    2. Configuration file
    3. Default values
    """

    # Environment variable mappings
    ENV_VARS = {
        "TRANSLATION_API_KEY": ("translation", "api_key"),
        "TRANSLATION_API_URL": ("translation", "api_url"),
        "TRANSLATION_TIMEOUT": ("translation", "timeout"),
        "TRANSLATION_MAX_RETRIES": ("translation", "max_retries"),
        "TRANSLATION_VERIFY_SSL": ("translation", "verify_ssl"),
        "LOG_LEVEL": ("logging", "level"),
        "LOG_FILE": ("logging", "file_path"),
        "DEFAULT_SOURCE_LANGUAGE": (None, "default_source_language"),
        "DEFAULT_TARGET_LANGUAGE": (None, "default_target_language"),
        "OUTPUT_DIRECTORY": (None, "output_directory"),
    }

    # Valid log levels
    VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(self, config_file_path: Optional[str] = None):
        """Initialize the config loader.

        Args:
            config_file_path: Optional path to a JSON configuration file
        """
        self._config_file_path = config_file_path
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def load(self) -> AppConfig:
        """Load and validate the application configuration.

        Returns:
            AppConfig: The validated configuration

        Raises:
            ConfigurationError: If configuration is invalid
            MissingAPIKeyError: If API key is not configured
        """
        # Start with defaults
        config_data = self._get_defaults()

        # Load from file if provided
        if self._config_file_path:
            file_config = self._load_from_file(self._config_file_path)
            config_data = self._merge_config(config_data, file_config)

        # Override with environment variables
        env_config = self._load_from_environment()
        config_data = self._merge_config(config_data, env_config)

        # Validate and build config object
        return self._build_config(config_data)

    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "translation": {
                "api_url": "https://api.translation-service.example.com/v1",
                "timeout": 30.0,
                "max_retries": 3,
                "verify_ssl": True,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "default_target_language": "en",
            "output_directory": "./output",
        }

    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from a JSON file.

        Args:
            file_path: Path to the configuration file

        Returns:
            dict: Configuration data from the file

        Raises:
            ConfigurationError: If the file cannot be read or parsed
        """
        path = Path(file_path)

        if not path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {file_path}",
                "Please check the file path or create the configuration file"
            )

        if not path.is_file():
            raise ConfigurationError(
                f"Configuration path is not a file: {file_path}",
                "Please provide a path to a JSON configuration file"
            )

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except PermissionError:
            raise ConfigurationError(
                f"Cannot read configuration file: {file_path}",
                "Permission denied. Check file permissions."
            )
        except IOError as e:
            raise ConfigurationError(
                f"Cannot read configuration file: {file_path}",
                f"I/O error: {e}"
            )

        if not content.strip():
            raise ConfigurationError(
                f"Configuration file is empty: {file_path}",
                "Please add valid JSON configuration to the file"
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {file_path}",
                f"Parse error at line {e.lineno}, column {e.colno}: {e.msg}"
            )

        if not isinstance(data, dict):
            raise ConfigurationError(
                f"Invalid configuration format in: {file_path}",
                f"Expected JSON object, got {type(data).__name__}"
            )

        self._logger.info(f"Loaded configuration from {file_path}")
        return data

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables.

        Returns:
            dict: Configuration data from environment
        """
        config: Dict[str, Any] = {}

        for env_var, (section, key) in self.ENV_VARS.items():
            value = os.environ.get(env_var)
            if value is None:
                continue

            # Convert value to appropriate type
            converted_value = self._convert_env_value(env_var, value)

            if section:
                if section not in config:
                    config[section] = {}
                config[section][key] = converted_value
            else:
                config[key] = converted_value

        return config

    def _convert_env_value(self, var_name: str, value: str) -> Any:
        """Convert environment variable string to appropriate type.

        Args:
            var_name: Name of the environment variable
            value: String value from environment

        Returns:
            Converted value

        Raises:
            InvalidConfigurationError: If value cannot be converted
        """
        # Boolean conversions
        if var_name in ("TRANSLATION_VERIFY_SSL",):
            lower_val = value.lower()
            if lower_val in ("true", "1", "yes", "on"):
                return True
            elif lower_val in ("false", "0", "no", "off"):
                return False
            else:
                raise InvalidConfigurationError(
                    var_name,
                    "boolean (true/false, 1/0, yes/no)",
                    value
                )

        # Integer conversions
        if var_name in ("TRANSLATION_MAX_RETRIES",):
            try:
                int_val = int(value)
                if int_val < 0:
                    raise InvalidConfigurationError(
                        var_name,
                        "non-negative integer",
                        value
                    )
                return int_val
            except ValueError:
                raise InvalidConfigurationError(var_name, "integer", value)

        # Float conversions
        if var_name in ("TRANSLATION_TIMEOUT",):
            try:
                float_val = float(value)
                if float_val <= 0:
                    raise InvalidConfigurationError(
                        var_name,
                        "positive number",
                        value
                    )
                return float_val
            except ValueError:
                raise InvalidConfigurationError(var_name, "number", value)

        # String values (no conversion needed)
        return value

    def _merge_config(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Values from 'override' take precedence over 'base'.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            dict: Merged configuration
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def _build_config(self, data: Dict[str, Any]) -> AppConfig:
        """Build and validate the AppConfig from configuration data.

        Args:
            data: Configuration dictionary

        Returns:
            AppConfig: Validated configuration object

        Raises:
            MissingAPIKeyError: If API key is missing
            InvalidConfigurationError: If values are invalid
        """
        # Validate required fields
        translation_data = data.get("translation", {})

        if not translation_data.get("api_key"):
            raise MissingAPIKeyError("translation-service")

        # Validate log level
        logging_data = data.get("logging", {})
        log_level = logging_data.get("level", "INFO").upper()
        if log_level not in self.VALID_LOG_LEVELS:
            raise InvalidConfigurationError(
                "LOG_LEVEL",
                f"one of {', '.join(self.VALID_LOG_LEVELS)}",
                log_level
            )
        logging_data["level"] = log_level

        # Build translation config
        translation_config = TranslationConfig(
            api_key=translation_data["api_key"],
            api_url=translation_data.get(
                "api_url",
                "https://api.translation-service.example.com/v1"
            ),
            timeout=float(translation_data.get("timeout", 30.0)),
            max_retries=int(translation_data.get("max_retries", 3)),
            verify_ssl=bool(translation_data.get("verify_ssl", True)),
        )

        # Build logging config
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            format=logging_data.get(
                "format",
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            file_path=logging_data.get("file_path"),
        )

        # Build and return main config
        return AppConfig(
            translation=translation_config,
            logging=logging_config,
            default_source_language=data.get("default_source_language"),
            default_target_language=data.get("default_target_language", "en"),
            output_directory=data.get("output_directory", "./output"),
        )


def load_config(config_file: Optional[str] = None) -> AppConfig:
    """Convenience function to load application configuration.

    Args:
        config_file: Optional path to configuration file

    Returns:
        AppConfig: The loaded configuration

    Raises:
        ConfigurationError: If configuration is invalid
    """
    loader = ConfigLoader(config_file)
    return loader.load()

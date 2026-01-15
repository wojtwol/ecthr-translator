"""
Custom exceptions for the ECTHR Translator.

This module provides a hierarchy of specific exception classes with clear,
descriptive error messages to aid debugging and provide meaningful feedback
to users and callers.
"""

from typing import Optional


class ECTHRTranslatorError(Exception):
    """Base exception for all ECTHR Translator errors.

    All custom exceptions in this package inherit from this class,
    making it easy to catch any translator-related error.
    """

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.details:
            return f"{self.message}. Details: {self.details}"
        return self.message


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(ECTHRTranslatorError):
    """Raised when there's an issue with configuration settings."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Raised when a required API key is not configured."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Missing API key for '{service_name}'",
            "Please set the appropriate environment variable or configuration file"
        )
        self.service_name = service_name


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, config_key: str, expected_format: str, actual_value: str):
        super().__init__(
            f"Invalid configuration for '{config_key}'",
            f"Expected {expected_format}, but got '{actual_value}'"
        )
        self.config_key = config_key


# ============================================================================
# File and Document Errors
# ============================================================================

class DocumentError(ECTHRTranslatorError):
    """Base exception for document-related errors."""
    pass


class DocumentNotFoundError(DocumentError):
    """Raised when a document file cannot be found."""

    def __init__(self, file_path: str):
        super().__init__(
            f"Document not found: '{file_path}'",
            "Please verify the file path exists and is accessible"
        )
        self.file_path = file_path


class DocumentReadError(DocumentError):
    """Raised when a document cannot be read."""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            f"Failed to read document: '{file_path}'",
            reason
        )
        self.file_path = file_path
        self.reason = reason


class DocumentWriteError(DocumentError):
    """Raised when a document cannot be written."""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            f"Failed to write document: '{file_path}'",
            reason
        )
        self.file_path = file_path
        self.reason = reason


class UnsupportedDocumentFormatError(DocumentError):
    """Raised when attempting to process an unsupported document format."""

    SUPPORTED_FORMATS = ['.txt', '.pdf', '.docx', '.html']

    def __init__(self, file_path: str, detected_format: str):
        super().__init__(
            f"Unsupported document format: '{detected_format}'",
            f"Supported formats are: {', '.join(self.SUPPORTED_FORMATS)}"
        )
        self.file_path = file_path
        self.detected_format = detected_format


class DocumentParseError(DocumentError):
    """Raised when document content cannot be parsed."""

    def __init__(self, file_path: str, reason: str, line_number: Optional[int] = None):
        location = f" at line {line_number}" if line_number else ""
        super().__init__(
            f"Failed to parse document: '{file_path}'{location}",
            reason
        )
        self.file_path = file_path
        self.line_number = line_number


class DocumentTooLargeError(DocumentError):
    """Raised when a document exceeds size limits."""

    def __init__(self, file_path: str, size_bytes: int, max_size_bytes: int):
        size_mb = size_bytes / (1024 * 1024)
        max_mb = max_size_bytes / (1024 * 1024)
        super().__init__(
            f"Document '{file_path}' is too large ({size_mb:.2f} MB)",
            f"Maximum allowed size is {max_mb:.2f} MB"
        )
        self.file_path = file_path
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes


# ============================================================================
# Translation Errors
# ============================================================================

class TranslationError(ECTHRTranslatorError):
    """Base exception for translation-related errors."""
    pass


class UnsupportedLanguageError(TranslationError):
    """Raised when an unsupported language is requested."""

    def __init__(self, language_code: str, supported_languages: list):
        super().__init__(
            f"Unsupported language: '{language_code}'",
            f"Supported languages are: {', '.join(supported_languages)}"
        )
        self.language_code = language_code
        self.supported_languages = supported_languages


class TranslationAPIError(TranslationError):
    """Raised when the translation API returns an error."""

    def __init__(self, status_code: int, api_message: str):
        super().__init__(
            f"Translation API error (HTTP {status_code})",
            api_message
        )
        self.status_code = status_code
        self.api_message = api_message


class TranslationTimeoutError(TranslationError):
    """Raised when a translation request times out."""

    def __init__(self, timeout_seconds: float, text_length: int):
        super().__init__(
            f"Translation request timed out after {timeout_seconds} seconds",
            f"Text length was {text_length} characters. Consider breaking into smaller chunks"
        )
        self.timeout_seconds = timeout_seconds
        self.text_length = text_length


class TranslationQuotaExceededError(TranslationError):
    """Raised when translation quota/rate limit is exceeded."""

    def __init__(self, retry_after_seconds: Optional[int] = None):
        retry_info = f"Retry after {retry_after_seconds} seconds" if retry_after_seconds else "Please try again later"
        super().__init__(
            "Translation quota exceeded",
            retry_info
        )
        self.retry_after_seconds = retry_after_seconds


class EmptyTextError(TranslationError):
    """Raised when attempting to translate empty text."""

    def __init__(self):
        super().__init__(
            "Cannot translate empty text",
            "Please provide non-empty text to translate"
        )


# ============================================================================
# Network and API Errors
# ============================================================================

class NetworkError(ECTHRTranslatorError):
    """Base exception for network-related errors."""
    pass


class ConnectionError(NetworkError):
    """Raised when unable to establish a network connection."""

    def __init__(self, host: str, reason: str):
        super().__init__(
            f"Failed to connect to '{host}'",
            reason
        )
        self.host = host


class SSLError(NetworkError):
    """Raised when SSL/TLS verification fails."""

    def __init__(self, host: str, reason: str):
        super().__init__(
            f"SSL/TLS verification failed for '{host}'",
            reason
        )
        self.host = host


class APIResponseError(NetworkError):
    """Raised when an API response cannot be parsed."""

    def __init__(self, expected_format: str, actual_content: str):
        # Truncate long content
        truncated = actual_content[:100] + "..." if len(actual_content) > 100 else actual_content
        super().__init__(
            f"Invalid API response format",
            f"Expected {expected_format}, received: {truncated}"
        )


class RetryExhaustedError(NetworkError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, operation: str, attempts: int, last_error: str):
        super().__init__(
            f"Operation '{operation}' failed after {attempts} attempts",
            f"Last error: {last_error}"
        )
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


# ============================================================================
# Validation Errors
# ============================================================================

class ValidationError(ECTHRTranslatorError):
    """Base exception for validation errors."""
    pass


class InvalidLanguageCodeError(ValidationError):
    """Raised when a language code format is invalid."""

    def __init__(self, language_code: str):
        super().__init__(
            f"Invalid language code format: '{language_code}'",
            "Language codes should be ISO 639-1 (e.g., 'en', 'fr') or ISO 639-2 (e.g., 'eng', 'fra')"
        )
        self.language_code = language_code


class InvalidCaseReferenceError(ValidationError):
    """Raised when an ECTHR case reference format is invalid."""

    def __init__(self, case_reference: str):
        super().__init__(
            f"Invalid ECTHR case reference: '{case_reference}'",
            "Expected format: 'Application no. XXXXX/YY' or similar ECTHR reference format"
        )
        self.case_reference = case_reference

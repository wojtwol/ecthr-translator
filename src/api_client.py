"""
API client for translation services.

This module provides a robust HTTP client with comprehensive error handling,
retry logic with exponential backoff, and timeout management.
"""

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlencode

from .exceptions import (
    MissingAPIKeyError,
    ConfigurationError,
    TranslationAPIError,
    TranslationTimeoutError,
    TranslationQuotaExceededError,
    ConnectionError,
    SSLError,
    APIResponseError,
    RetryExhaustedError,
    NetworkError,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt using exponential backoff.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            float: Delay in seconds before next retry
        """
        delay = self.base_delay_seconds * (self.exponential_base ** attempt)
        return min(delay, self.max_delay_seconds)


@dataclass
class APIResponse:
    """Represents an API response."""
    status_code: int
    body: str
    headers: Dict[str, str]

    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300

    def json(self) -> Dict[str, Any]:
        """Parse response body as JSON.

        Returns:
            dict: Parsed JSON data

        Raises:
            APIResponseError: If body is not valid JSON
        """
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as e:
            raise APIResponseError(
                "JSON",
                f"Invalid JSON at position {e.pos}: {self.body[:200]}"
            )


class APIClient:
    """HTTP client for translation API calls with robust error handling.

    This client provides:
    - Automatic retry with exponential backoff for transient failures
    - Configurable timeouts
    - Comprehensive error handling with clear messages
    - Rate limit handling
    """

    DEFAULT_TIMEOUT = 30.0  # seconds
    DEFAULT_BASE_URL = "https://api.translation-service.example.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_config: Optional[RetryConfig] = None,
        verify_ssl: bool = True,
    ):
        """Initialize the API client.

        Args:
            api_key: API key for authentication. If not provided, reads from
                    TRANSLATION_API_KEY environment variable.
            base_url: Base URL for the translation API. If not provided, reads
                     from TRANSLATION_API_URL environment variable or uses default.
            timeout: Request timeout in seconds
            retry_config: Configuration for retry behavior
            verify_ssl: Whether to verify SSL certificates

        Raises:
            MissingAPIKeyError: If no API key is provided or found
            ConfigurationError: If configuration is invalid
        """
        # Get API key
        self._api_key = api_key or os.environ.get("TRANSLATION_API_KEY")
        if not self._api_key:
            raise MissingAPIKeyError("translation-service")

        # Validate API key format (basic check)
        if len(self._api_key) < 10:
            raise ConfigurationError(
                "API key appears to be invalid",
                "API key is too short. Please check your API key configuration."
            )

        # Get base URL
        self._base_url = (
            base_url
            or os.environ.get("TRANSLATION_API_URL")
            or self.DEFAULT_BASE_URL
        )

        # Validate base URL
        if not self._base_url.startswith(('http://', 'https://')):
            raise ConfigurationError(
                f"Invalid base URL: {self._base_url}",
                "Base URL must start with 'http://' or 'https://'"
            )

        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._retry_config = retry_config or RetryConfig()
        self._verify_ssl = verify_ssl
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Create SSL context
        self._ssl_context = self._create_ssl_context()

        self._logger.debug(
            f"API client initialized: base_url={self._base_url}, "
            f"timeout={self._timeout}s, verify_ssl={verify_ssl}"
        )

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for HTTPS requests.

        Returns:
            ssl.SSLContext: Configured SSL context
        """
        if self._verify_ssl:
            context = ssl.create_default_context()
        else:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self._logger.warning(
                "SSL verification is disabled. This is insecure for production use."
            )
        return context

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> APIResponse:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base URL)
            data: Request body data (will be JSON-encoded)
            params: URL query parameters
            timeout: Override default timeout for this request

        Returns:
            APIResponse: The response from the API

        Raises:
            ConnectionError: If connection fails
            SSLError: If SSL verification fails
            TranslationTimeoutError: If request times out
            TranslationQuotaExceededError: If rate limited
            TranslationAPIError: If API returns an error
            RetryExhaustedError: If all retry attempts fail
        """
        url = urljoin(self._base_url, endpoint)
        if params:
            url = f"{url}?{urlencode(params)}"

        request_timeout = timeout or self._timeout
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ECTHR-Translator/0.1.0",
        }

        # Prepare request body
        body = None
        if data:
            try:
                body = json.dumps(data).encode('utf-8')
            except (TypeError, ValueError) as e:
                raise ConfigurationError(
                    "Failed to encode request data",
                    f"Data is not JSON-serializable: {e}"
                )

        # Retry loop
        last_error = None
        for attempt in range(self._retry_config.max_attempts):
            try:
                return self._execute_request(
                    method, url, headers, body, request_timeout
                )

            except TranslationQuotaExceededError as e:
                # Rate limited - use retry-after if provided
                if e.retry_after_seconds and attempt < self._retry_config.max_attempts - 1:
                    delay = e.retry_after_seconds
                    self._logger.warning(
                        f"Rate limited. Waiting {delay}s before retry "
                        f"(attempt {attempt + 1}/{self._retry_config.max_attempts})"
                    )
                    time.sleep(delay)
                    last_error = str(e)
                    continue
                raise

            except (ConnectionError, TranslationTimeoutError) as e:
                # Transient error - retry with backoff
                last_error = str(e)
                if attempt < self._retry_config.max_attempts - 1:
                    delay = self._retry_config.get_delay(attempt)
                    self._logger.warning(
                        f"Request failed: {e}. Retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self._retry_config.max_attempts})"
                    )
                    time.sleep(delay)
                    continue
                raise

            except TranslationAPIError as e:
                # Check if status code is retryable
                if (
                    e.status_code in self._retry_config.retryable_status_codes
                    and attempt < self._retry_config.max_attempts - 1
                ):
                    delay = self._retry_config.get_delay(attempt)
                    self._logger.warning(
                        f"Server error (HTTP {e.status_code}). Retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self._retry_config.max_attempts})"
                    )
                    time.sleep(delay)
                    last_error = str(e)
                    continue
                raise

        # All retries exhausted
        raise RetryExhaustedError(
            f"{method} {endpoint}",
            self._retry_config.max_attempts,
            last_error or "Unknown error"
        )

    def _execute_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        timeout: float,
    ) -> APIResponse:
        """Execute a single HTTP request without retry.

        This method handles the low-level HTTP communication and translates
        various error conditions into appropriate exceptions.
        """
        self._logger.debug(f"Executing {method} {url} (timeout={timeout}s)")

        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
                context=self._ssl_context,
            ) as response:
                response_body = response.read().decode('utf-8')
                response_headers = dict(response.getheaders())

                self._logger.debug(
                    f"Response: {response.status} "
                    f"({len(response_body)} bytes)"
                )

                return APIResponse(
                    status_code=response.status,
                    body=response_body,
                    headers=response_headers,
                )

        except urllib.error.HTTPError as e:
            # Read error response body
            try:
                error_body = e.read().decode('utf-8')
                error_data = json.loads(error_body)
                error_message = error_data.get('error', {}).get('message', error_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                error_message = str(e)

            self._logger.error(
                f"HTTP error {e.code}: {error_message}"
            )

            # Handle specific error codes
            if e.code == 401:
                raise TranslationAPIError(
                    e.code,
                    "Authentication failed. Please check your API key."
                )
            elif e.code == 403:
                raise TranslationAPIError(
                    e.code,
                    "Access forbidden. Your API key may not have permission for this operation."
                )
            elif e.code == 404:
                raise TranslationAPIError(
                    e.code,
                    f"Resource not found: {url}"
                )
            elif e.code == 429:
                # Extract retry-after header
                retry_after = e.headers.get('Retry-After')
                retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
                raise TranslationQuotaExceededError(retry_seconds)
            else:
                raise TranslationAPIError(e.code, error_message)

        except urllib.error.URLError as e:
            # Handle connection errors
            reason = str(e.reason)

            if isinstance(e.reason, ssl.SSLError):
                raise SSLError(
                    self._base_url,
                    f"SSL certificate verification failed: {reason}"
                )
            elif isinstance(e.reason, TimeoutError):
                raise TranslationTimeoutError(timeout, 0)
            elif "Name or service not known" in reason or "getaddrinfo failed" in reason:
                raise ConnectionError(
                    self._base_url,
                    "DNS resolution failed. Please check your internet connection and the API URL."
                )
            elif "Connection refused" in reason:
                raise ConnectionError(
                    self._base_url,
                    "Connection refused. The server may be down or the URL may be incorrect."
                )
            elif "Network is unreachable" in reason:
                raise ConnectionError(
                    self._base_url,
                    "Network is unreachable. Please check your internet connection."
                )
            else:
                raise ConnectionError(self._base_url, reason)

        except TimeoutError:
            raise TranslationTimeoutError(timeout, 0)

        except ssl.SSLError as e:
            raise SSLError(
                self._base_url,
                f"SSL error: {e}"
            )

        except OSError as e:
            raise ConnectionError(
                self._base_url,
                f"Network error: {e}"
            )

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate text using the translation API.

        Args:
            text: The text to translate
            target_language: Target language code
            source_language: Optional source language code (auto-detect if not provided)

        Returns:
            dict: Translation result with keys:
                - translated_text: The translated text
                - detected_language: Detected source language (if auto-detected)
                - confidence_score: Confidence score (0-1)

        Raises:
            TranslationAPIError: If the API returns an error
            TranslationTimeoutError: If the request times out
            NetworkError: If a network error occurs
        """
        data = {
            "text": text,
            "target_language": target_language,
        }
        if source_language:
            data["source_language"] = source_language

        # Adjust timeout based on text length
        # Longer texts may need more processing time
        text_length = len(text)
        timeout = self._timeout
        if text_length > 10000:
            timeout = self._timeout * 2
            self._logger.debug(
                f"Increased timeout to {timeout}s for large text ({text_length} chars)"
            )

        try:
            response = self._make_request(
                "POST",
                "/translate",
                data=data,
                timeout=timeout,
            )

            if not response.is_success:
                raise TranslationAPIError(
                    response.status_code,
                    f"Unexpected response status: {response.status_code}"
                )

            result = response.json()

            # Validate response structure
            if "translated_text" not in result:
                raise APIResponseError(
                    "translation response with 'translated_text' field",
                    response.body
                )

            return result

        except TranslationTimeoutError:
            raise TranslationTimeoutError(timeout, text_length)

    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect the language of the given text.

        Args:
            text: The text to analyze

        Returns:
            dict: Detection result with keys:
                - language: Detected language code
                - confidence: Confidence score (0-1)
                - alternatives: List of alternative language detections

        Raises:
            TranslationAPIError: If the API returns an error
            NetworkError: If a network error occurs
        """
        response = self._make_request(
            "POST",
            "/detect",
            data={"text": text},
        )

        if not response.is_success:
            raise TranslationAPIError(
                response.status_code,
                "Language detection failed"
            )

        result = response.json()

        if "language" not in result:
            raise APIResponseError(
                "language detection response with 'language' field",
                response.body
            )

        return result

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages from the API.

        Returns:
            list: List of language objects with 'code' and 'name' keys

        Raises:
            TranslationAPIError: If the API returns an error
            NetworkError: If a network error occurs
        """
        response = self._make_request("GET", "/languages")

        if not response.is_success:
            raise TranslationAPIError(
                response.status_code,
                "Failed to get supported languages"
            )

        result = response.json()

        if "languages" not in result:
            raise APIResponseError(
                "languages response with 'languages' field",
                response.body
            )

        return result["languages"]

    def health_check(self) -> bool:
        """Check if the translation API is healthy.

        Returns:
            bool: True if the API is healthy, False otherwise
        """
        try:
            response = self._make_request(
                "GET",
                "/health",
                timeout=5.0,  # Short timeout for health check
            )
            return response.is_success
        except (NetworkError, TranslationAPIError) as e:
            self._logger.warning(f"Health check failed: {e}")
            return False

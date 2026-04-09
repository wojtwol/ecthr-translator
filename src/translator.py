"""
Translation service for ECTHR documents.

This module provides the core translation functionality with comprehensive
error handling for various failure scenarios.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

from .exceptions import (
    EmptyTextError,
    UnsupportedLanguageError,
    TranslationError,
    InvalidLanguageCodeError,
)

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages for ECTHR document translation."""
    ENGLISH = "en"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    SPANISH = "es"
    RUSSIAN = "ru"
    TURKISH = "tr"
    POLISH = "pl"
    ROMANIAN = "ro"
    UKRAINIAN = "uk"
    GREEK = "el"
    DUTCH = "nl"
    PORTUGUESE = "pt"
    BULGARIAN = "bg"
    CZECH = "cs"
    HUNGARIAN = "hu"

    @classmethod
    def from_code(cls, code: str) -> "Language":
        """Convert a language code to a Language enum.

        Args:
            code: ISO 639-1 language code (e.g., 'en', 'fr')

        Returns:
            Language: The corresponding Language enum value

        Raises:
            InvalidLanguageCodeError: If the code format is invalid
            UnsupportedLanguageError: If the language is not supported
        """
        if not code:
            raise InvalidLanguageCodeError(code)

        # Validate language code format (ISO 639-1: 2 letters, ISO 639-2: 3 letters)
        code_lower = code.lower().strip()
        if not re.match(r'^[a-z]{2,3}$', code_lower):
            raise InvalidLanguageCodeError(code)

        # Try to find matching language
        for lang in cls:
            if lang.value == code_lower:
                return lang

        # Language code valid but not supported
        supported = [lang.value for lang in cls]
        raise UnsupportedLanguageError(code_lower, supported)

    @classmethod
    def get_supported_codes(cls) -> List[str]:
        """Return list of supported language codes."""
        return [lang.value for lang in cls]


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    source_text: str
    translated_text: str
    source_language: Language
    target_language: Language
    confidence_score: Optional[float] = None
    detected_language: Optional[Language] = None
    warnings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "source_language": self.source_language.value,
            "target_language": self.target_language.value,
            "confidence_score": self.confidence_score,
            "detected_language": self.detected_language.value if self.detected_language else None,
            "warnings": self.warnings,
        }


class TranslationService:
    """Service for translating ECTHR legal documents.

    This class provides translation capabilities with comprehensive error
    handling and validation.
    """

    # Maximum text length per translation request (characters)
    MAX_TEXT_LENGTH = 50000

    # Minimum text length to warn about potential issues
    MIN_MEANINGFUL_LENGTH = 10

    def __init__(self, api_client: "APIClient"):
        """Initialize the translation service.

        Args:
            api_client: The API client to use for translation requests

        Raises:
            ValueError: If api_client is None
        """
        if api_client is None:
            raise ValueError(
                "api_client cannot be None. Please provide a valid APIClient instance."
            )
        self._api_client = api_client
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """Translate text to the target language.

        Args:
            text: The text to translate
            target_language: Target language code (ISO 639-1)
            source_language: Optional source language code. If not provided,
                           the language will be auto-detected.

        Returns:
            TranslationResult: The translation result with metadata

        Raises:
            EmptyTextError: If the text is empty or whitespace-only
            InvalidLanguageCodeError: If language code format is invalid
            UnsupportedLanguageError: If the language is not supported
            TranslationError: If translation fails
        """
        # Validate input text
        self._validate_text(text)

        # Validate and convert language codes
        target_lang = Language.from_code(target_language)
        source_lang = Language.from_code(source_language) if source_language else None

        # Collect warnings
        warnings = []

        # Check for potential issues
        if len(text.strip()) < self.MIN_MEANINGFUL_LENGTH:
            warnings.append(
                f"Text is very short ({len(text.strip())} chars). "
                "Translation quality may be affected."
            )

        # Check if source and target are the same
        if source_lang and source_lang == target_lang:
            self._logger.info(
                f"Source and target language are the same ({target_lang.value}). "
                "Returning original text."
            )
            return TranslationResult(
                source_text=text,
                translated_text=text,
                source_language=target_lang,
                target_language=target_lang,
                confidence_score=1.0,
                warnings=["Source and target languages are identical."] if warnings else None,
            )

        # Perform translation via API
        try:
            self._logger.debug(
                f"Translating {len(text)} chars from "
                f"{source_lang.value if source_lang else 'auto'} to {target_lang.value}"
            )

            result = self._api_client.translate(
                text=text,
                target_language=target_lang.value,
                source_language=source_lang.value if source_lang else None,
            )

            # Build and return result
            detected_lang = None
            if result.get("detected_language"):
                try:
                    detected_lang = Language.from_code(result["detected_language"])
                except (InvalidLanguageCodeError, UnsupportedLanguageError):
                    warnings.append(
                        f"Detected language '{result['detected_language']}' is not recognized."
                    )

            return TranslationResult(
                source_text=text,
                translated_text=result["translated_text"],
                source_language=source_lang or detected_lang or target_lang,
                target_language=target_lang,
                confidence_score=result.get("confidence_score"),
                detected_language=detected_lang,
                warnings=warnings if warnings else None,
            )

        except TranslationError:
            # Re-raise translation-specific errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors with context
            self._logger.error(f"Unexpected error during translation: {e}", exc_info=True)
            raise TranslationError(
                f"Translation failed unexpectedly",
                str(e)
            ) from e

    def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> List[TranslationResult]:
        """Translate multiple texts to the target language.

        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Optional source language code

        Returns:
            List of TranslationResult objects

        Raises:
            ValueError: If texts list is empty
            TranslationError: If translation fails for any text
        """
        if not texts:
            raise ValueError(
                "Cannot translate empty list. Please provide at least one text to translate."
            )

        if not isinstance(texts, list):
            raise TypeError(
                f"Expected list of texts, got {type(texts).__name__}. "
                "Use translate() for single text translation."
            )

        results = []
        errors = []

        for i, text in enumerate(texts):
            try:
                result = self.translate(text, target_language, source_language)
                results.append(result)
            except EmptyTextError:
                # Skip empty texts but record them
                errors.append(f"Text at index {i} is empty and was skipped")
                self._logger.warning(f"Skipping empty text at index {i}")
            except TranslationError as e:
                # Record error but continue with other texts
                errors.append(f"Text at index {i} failed: {e.message}")
                self._logger.error(f"Translation failed for text at index {i}: {e}")

        # If all translations failed, raise an error
        if not results and errors:
            raise TranslationError(
                "All translations failed",
                f"Errors: {'; '.join(errors)}"
            )

        # Log any partial failures
        if errors:
            self._logger.warning(
                f"Batch translation completed with {len(errors)} error(s): {errors}"
            )

        return results

    def _validate_text(self, text: str) -> None:
        """Validate text before translation.

        Args:
            text: The text to validate

        Raises:
            EmptyTextError: If text is empty or whitespace-only
            TranslationError: If text exceeds maximum length
        """
        if text is None:
            raise EmptyTextError()

        if not isinstance(text, str):
            raise TypeError(
                f"Expected string, got {type(text).__name__}. "
                "Please provide text as a string."
            )

        stripped = text.strip()
        if not stripped:
            raise EmptyTextError()

        if len(stripped) > self.MAX_TEXT_LENGTH:
            raise TranslationError(
                f"Text exceeds maximum length of {self.MAX_TEXT_LENGTH:,} characters",
                f"Provided text has {len(stripped):,} characters. "
                "Please split the text into smaller chunks."
            )

    def detect_language(self, text: str) -> Language:
        """Detect the language of the given text.

        Args:
            text: The text to analyze

        Returns:
            Language: The detected language

        Raises:
            EmptyTextError: If text is empty
            TranslationError: If detection fails
        """
        self._validate_text(text)

        try:
            result = self._api_client.detect_language(text)
            detected_code = result.get("language")

            if not detected_code:
                raise TranslationError(
                    "Language detection returned no result",
                    "The API did not return a detected language code"
                )

            return Language.from_code(detected_code)

        except (InvalidLanguageCodeError, UnsupportedLanguageError) as e:
            raise TranslationError(
                "Detected language is not supported",
                str(e)
            ) from e
        except TranslationError:
            raise
        except Exception as e:
            self._logger.error(f"Language detection failed: {e}", exc_info=True)
            raise TranslationError(
                "Language detection failed",
                str(e)
            ) from e

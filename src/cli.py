"""
Command-line interface for ECTHR Translator.

This module provides a user-friendly CLI with comprehensive error handling
and clear, actionable error messages.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List

from .exceptions import (
    ECTHRTranslatorError,
    MissingAPIKeyError,
    ConfigurationError,
    DocumentNotFoundError,
    DocumentReadError,
    UnsupportedDocumentFormatError,
    TranslationError,
    UnsupportedLanguageError,
    NetworkError,
    ConnectionError,
    TranslationTimeoutError,
    TranslationQuotaExceededError,
    RetryExhaustedError,
)
from .config import load_config, AppConfig
from .api_client import APIClient, RetryConfig
from .translator import TranslationService, Language
from .document_parser import parse_document, write_document, DocumentParserFactory

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    @classmethod
    def disable(cls):
        """Disable colors for non-terminal output."""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.RESET = ""
        cls.BOLD = ""


def setup_logging(config: AppConfig) -> None:
    """Configure logging based on application configuration.

    Args:
        config: Application configuration
    """
    log_level = getattr(logging, config.logging.level)

    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if config.logging.file_path:
        try:
            file_handler = logging.FileHandler(config.logging.file_path)
            handlers.append(file_handler)
        except (PermissionError, IOError) as e:
            print(
                f"{Colors.YELLOW}Warning: Could not create log file "
                f"'{config.logging.file_path}': {e}{Colors.RESET}",
                file=sys.stderr
            )

    logging.basicConfig(
        level=log_level,
        format=config.logging.format,
        handlers=handlers,
    )


def print_error(title: str, message: str, suggestion: Optional[str] = None) -> None:
    """Print a formatted error message to stderr.

    Args:
        title: Short error title
        message: Detailed error message
        suggestion: Optional suggestion for how to fix the error
    """
    print(f"\n{Colors.RED}{Colors.BOLD}Error: {title}{Colors.RESET}", file=sys.stderr)
    print(f"  {message}", file=sys.stderr)
    if suggestion:
        print(f"\n{Colors.YELLOW}Suggestion:{Colors.RESET} {suggestion}", file=sys.stderr)
    print(file=sys.stderr)


def print_success(message: str) -> None:
    """Print a formatted success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {message}")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="ecthr-translator",
        description="Translate European Court of Human Rights legal documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s document.txt -t fr
    Translate document.txt to French

  %(prog)s document.txt -s en -t de -o translated.txt
    Translate from English to German, save to translated.txt

  %(prog)s --list-languages
    Show all supported languages

Environment Variables:
  TRANSLATION_API_KEY    API key for the translation service (required)
  TRANSLATION_API_URL    Custom API endpoint URL
  TRANSLATION_TIMEOUT    Request timeout in seconds
  LOG_LEVEL              Logging level (DEBUG, INFO, WARNING, ERROR)
        """,
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the document to translate",
    )

    parser.add_argument(
        "-t", "--target",
        dest="target_language",
        help="Target language code (e.g., 'en', 'fr', 'de')",
    )

    parser.add_argument(
        "-s", "--source",
        dest="source_language",
        help="Source language code (auto-detect if not specified)",
    )

    parser.add_argument(
        "-o", "--output",
        dest="output_file",
        help="Output file path (defaults to input_file.translated.ext)",
    )

    parser.add_argument(
        "-c", "--config",
        dest="config_file",
        help="Path to configuration file (JSON)",
    )

    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="List all supported languages and exit",
    )

    parser.add_argument(
        "--detect",
        action="store_true",
        help="Detect the language of the input document and exit",
    )

    parser.add_argument(
        "--formats",
        action="store_true",
        help="List supported document formats and exit",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser


def list_languages() -> int:
    """Print supported languages and return exit code."""
    print("Supported Languages:")
    print("-" * 40)
    for lang in Language:
        print(f"  {lang.value:5} - {lang.name.title()}")
    return 0


def list_formats() -> int:
    """Print supported document formats and return exit code."""
    formats = DocumentParserFactory.get_supported_formats()
    print("Supported Document Formats:")
    print("-" * 40)
    for fmt in formats:
        print(f"  {fmt}")
    return 0


def handle_translation_error(error: ECTHRTranslatorError) -> int:
    """Handle translation-related errors with user-friendly messages.

    Args:
        error: The error that occurred

    Returns:
        int: Exit code
    """
    if isinstance(error, MissingAPIKeyError):
        print_error(
            "API Key Not Configured",
            str(error),
            f"Set the {error.service_name.upper().replace('-', '_')}_API_KEY "
            "environment variable or add it to your config file."
        )
        return 2

    elif isinstance(error, ConfigurationError):
        print_error(
            "Configuration Error",
            str(error),
            "Check your configuration file and environment variables."
        )
        return 2

    elif isinstance(error, DocumentNotFoundError):
        print_error(
            "File Not Found",
            str(error),
            f"Verify the file path is correct: {error.file_path}"
        )
        return 3

    elif isinstance(error, DocumentReadError):
        print_error(
            "Cannot Read File",
            str(error),
            "Check file permissions and ensure the file is readable."
        )
        return 3

    elif isinstance(error, UnsupportedDocumentFormatError):
        formats = DocumentParserFactory.get_supported_formats()
        print_error(
            "Unsupported File Format",
            str(error),
            f"Supported formats: {', '.join(formats)}"
        )
        return 3

    elif isinstance(error, UnsupportedLanguageError):
        print_error(
            "Unsupported Language",
            str(error),
            "Run with --list-languages to see supported languages."
        )
        return 4

    elif isinstance(error, TranslationQuotaExceededError):
        retry_msg = ""
        if error.retry_after_seconds:
            retry_msg = f" Try again in {error.retry_after_seconds} seconds."
        print_error(
            "Rate Limit Exceeded",
            str(error),
            f"You've exceeded the API rate limit.{retry_msg}"
        )
        return 5

    elif isinstance(error, TranslationTimeoutError):
        print_error(
            "Request Timed Out",
            str(error),
            "Try increasing the timeout or breaking the document into smaller parts."
        )
        return 5

    elif isinstance(error, ConnectionError):
        print_error(
            "Connection Failed",
            str(error),
            "Check your internet connection and the API URL."
        )
        return 6

    elif isinstance(error, RetryExhaustedError):
        print_error(
            "Operation Failed After Retries",
            str(error),
            "The service may be temporarily unavailable. Try again later."
        )
        return 6

    elif isinstance(error, NetworkError):
        print_error(
            "Network Error",
            str(error),
            "Check your internet connection and try again."
        )
        return 6

    elif isinstance(error, TranslationError):
        print_error(
            "Translation Failed",
            str(error),
            "Check the error details above for more information."
        )
        return 7

    else:
        print_error(
            "Error",
            str(error),
            "An unexpected error occurred."
        )
        return 1


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    parser = create_argument_parser()
    parsed_args = parser.parse_args(args)

    # Disable colors if requested or not a terminal
    if parsed_args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Handle info-only commands
    if parsed_args.list_languages:
        return list_languages()

    if parsed_args.formats:
        return list_formats()

    # Validate required arguments for translation
    if not parsed_args.input_file:
        print_error(
            "Missing Input File",
            "No input file specified.",
            "Provide a document to translate: ecthr-translator <input_file> -t <language>"
        )
        return 1

    if not parsed_args.target_language and not parsed_args.detect:
        print_error(
            "Missing Target Language",
            "No target language specified.",
            "Use -t/--target to specify the target language (e.g., -t fr for French)"
        )
        return 1

    # Load configuration
    try:
        config = load_config(parsed_args.config_file)
    except ECTHRTranslatorError as e:
        return handle_translation_error(e)

    # Override log level if verbose/quiet
    if parsed_args.verbose:
        config.logging.level = "DEBUG"
    elif parsed_args.quiet:
        config.logging.level = "ERROR"

    setup_logging(config)
    logger = logging.getLogger(__name__)

    try:
        # Parse input document
        if not parsed_args.quiet:
            print_info(f"Reading document: {parsed_args.input_file}")

        document = parse_document(parsed_args.input_file)

        if not parsed_args.quiet:
            print_info(
                f"Document loaded: {document.word_count:,} words, "
                f"{document.character_count:,} characters"
            )

        # Create API client and translation service
        retry_config = RetryConfig(max_attempts=config.translation.max_retries)
        api_client = APIClient(
            api_key=config.translation.api_key,
            base_url=config.translation.api_url,
            timeout=config.translation.timeout,
            retry_config=retry_config,
            verify_ssl=config.translation.verify_ssl,
        )
        translator = TranslationService(api_client)

        # Handle language detection
        if parsed_args.detect:
            if not parsed_args.quiet:
                print_info("Detecting language...")

            detected = translator.detect_language(document.content)
            print(f"Detected language: {detected.value} ({detected.name})")
            return 0

        # Perform translation
        if not parsed_args.quiet:
            source_info = parsed_args.source_language or "auto-detect"
            print_info(
                f"Translating from {source_info} to {parsed_args.target_language}..."
            )

        result = translator.translate(
            text=document.content,
            target_language=parsed_args.target_language,
            source_language=parsed_args.source_language,
        )

        # Print any warnings
        if result.warnings and not parsed_args.quiet:
            for warning in result.warnings:
                print(f"{Colors.YELLOW}Warning:{Colors.RESET} {warning}", file=sys.stderr)

        # Determine output path
        if parsed_args.output_file:
            output_path = parsed_args.output_file
        else:
            input_path = Path(parsed_args.input_file)
            output_path = str(
                input_path.parent
                / f"{input_path.stem}.{parsed_args.target_language}{input_path.suffix}"
            )

        # Write output
        write_document(output_path, result.translated_text, create_dirs=True)

        if not parsed_args.quiet:
            print_success(f"Translation saved to: {output_path}")

        return 0

    except ECTHRTranslatorError as e:
        logger.error(f"Translation error: {e}", exc_info=parsed_args.verbose)
        return handle_translation_error(e)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130

    except Exception as e:
        logger.exception("Unexpected error")
        print_error(
            "Unexpected Error",
            str(e),
            "This is likely a bug. Please report it with the error details."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

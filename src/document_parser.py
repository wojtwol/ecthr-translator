"""
Document parsing module for ECTHR Translator.

This module provides functionality to read and parse various document formats
with comprehensive error handling for file operations.
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Type

from .exceptions import (
    DocumentNotFoundError,
    DocumentReadError,
    DocumentWriteError,
    UnsupportedDocumentFormatError,
    DocumentParseError,
    DocumentTooLargeError,
    DocumentError,
)

logger = logging.getLogger(__name__)


# Maximum file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass
class ParsedDocument:
    """Represents a parsed document with its content and metadata."""
    file_path: str
    content: str
    format: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    sections: List[str] = field(default_factory=list)
    word_count: int = 0
    character_count: int = 0

    def __post_init__(self):
        """Calculate word and character counts after initialization."""
        if self.content:
            self.character_count = len(self.content)
            self.word_count = len(self.content.split())


class DocumentParser(ABC):
    """Abstract base class for document parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        pass

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse the document and return its content.

        Args:
            file_path: Path to the document file

        Returns:
            ParsedDocument: The parsed document with content and metadata

        Raises:
            DocumentError: If parsing fails
        """
        pass

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to the document file

        Returns:
            bool: True if this parser can handle the file
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions


class TextDocumentParser(DocumentParser):
    """Parser for plain text documents (.txt)."""

    # Common text file encodings to try
    ENCODINGS = ['utf-8', 'utf-16', 'latin-1', 'cp1252', 'iso-8859-1']

    @property
    def supported_extensions(self) -> List[str]:
        return ['.txt', '.text']

    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a plain text document.

        Args:
            file_path: Path to the text file

        Returns:
            ParsedDocument: The parsed document

        Raises:
            DocumentNotFoundError: If the file doesn't exist
            DocumentReadError: If the file can't be read
            DocumentTooLargeError: If the file exceeds size limits
        """
        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            raise DocumentNotFoundError(str(file_path))

        if not path.is_file():
            raise DocumentReadError(
                str(file_path),
                f"Path exists but is not a file (it's a {self._get_path_type(path)})"
            )

        # Check file size
        try:
            file_size = path.stat().st_size
        except OSError as e:
            raise DocumentReadError(
                str(file_path),
                f"Could not determine file size: {e}"
            )

        if file_size > MAX_FILE_SIZE:
            raise DocumentTooLargeError(str(file_path), file_size, MAX_FILE_SIZE)

        if file_size == 0:
            raise DocumentReadError(
                str(file_path),
                "File is empty (0 bytes)"
            )

        # Try to read file with different encodings
        content = None
        successful_encoding = None
        last_error = None

        for encoding in self.ENCODINGS:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
                successful_encoding = encoding
                break
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except PermissionError:
                raise DocumentReadError(
                    str(file_path),
                    "Permission denied. Check file permissions."
                )
            except IOError as e:
                raise DocumentReadError(
                    str(file_path),
                    f"I/O error while reading file: {e}"
                )

        if content is None:
            raise DocumentReadError(
                str(file_path),
                f"Could not decode file with any supported encoding. "
                f"Tried: {', '.join(self.ENCODINGS)}. Last error: {last_error}"
            )

        logger.debug(
            f"Successfully read '{file_path}' using {successful_encoding} encoding"
        )

        return ParsedDocument(
            file_path=str(file_path),
            content=content,
            format='txt',
            metadata={
                'encoding': successful_encoding,
                'file_size': file_size,
            }
        )

    def _get_path_type(self, path: Path) -> str:
        """Get human-readable description of path type."""
        if path.is_dir():
            return "directory"
        elif path.is_symlink():
            return "symbolic link"
        else:
            return "unknown type"


class HTMLDocumentParser(DocumentParser):
    """Parser for HTML documents."""

    @property
    def supported_extensions(self) -> List[str]:
        return ['.html', '.htm', '.xhtml']

    def parse(self, file_path: str) -> ParsedDocument:
        """Parse an HTML document, extracting text content.

        Args:
            file_path: Path to the HTML file

        Returns:
            ParsedDocument: The parsed document with extracted text

        Raises:
            DocumentError: If parsing fails
        """
        # First, read the file as text
        text_parser = TextDocumentParser()
        raw_doc = text_parser.parse(file_path)

        try:
            # Extract text content from HTML
            content = self._extract_text_from_html(raw_doc.content)

            # Extract metadata
            metadata = raw_doc.metadata.copy()
            metadata['original_format'] = 'html'
            metadata['title'] = self._extract_title(raw_doc.content)

            return ParsedDocument(
                file_path=str(file_path),
                content=content,
                format='html',
                metadata=metadata,
            )

        except Exception as e:
            raise DocumentParseError(
                str(file_path),
                f"Failed to parse HTML content: {e}"
            )

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML content.

        This is a simple implementation. For production use, consider
        using BeautifulSoup or lxml for more robust parsing.
        """
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # Replace common HTML entities
        entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&#39;': "'",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)

        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _extract_title(self, html_content: str) -> Optional[str]:
        """Extract the title from HTML content."""
        match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None


class DocumentParserFactory:
    """Factory for creating appropriate document parsers.

    This class manages the registry of parsers and creates the appropriate
    parser based on file extension.
    """

    _parsers: Dict[str, Type[DocumentParser]] = {}
    _instances: Dict[str, DocumentParser] = {}

    @classmethod
    def register_parser(cls, parser_class: Type[DocumentParser]) -> None:
        """Register a parser class for its supported extensions.

        Args:
            parser_class: The parser class to register
        """
        instance = parser_class()
        for ext in instance.supported_extensions:
            cls._parsers[ext.lower()] = parser_class
            logger.debug(f"Registered {parser_class.__name__} for extension '{ext}'")

    @classmethod
    def get_parser(cls, file_path: str) -> DocumentParser:
        """Get the appropriate parser for a file.

        Args:
            file_path: Path to the document file

        Returns:
            DocumentParser: A parser instance for the file type

        Raises:
            UnsupportedDocumentFormatError: If no parser exists for the file type
        """
        ext = Path(file_path).suffix.lower()

        if not ext:
            raise UnsupportedDocumentFormatError(
                file_path,
                "(no extension)"
            )

        if ext not in cls._parsers:
            raise UnsupportedDocumentFormatError(file_path, ext)

        # Cache parser instances
        if ext not in cls._instances:
            cls._instances[ext] = cls._parsers[ext]()

        return cls._instances[ext]

    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Return list of all supported file extensions."""
        return list(cls._parsers.keys())

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if a file format is supported.

        Args:
            file_path: Path to the document file

        Returns:
            bool: True if the format is supported
        """
        ext = Path(file_path).suffix.lower()
        return ext in cls._parsers


# Register built-in parsers
DocumentParserFactory.register_parser(TextDocumentParser)
DocumentParserFactory.register_parser(HTMLDocumentParser)


def parse_document(file_path: str) -> ParsedDocument:
    """Parse a document file.

    This is the main entry point for document parsing. It automatically
    selects the appropriate parser based on the file extension.

    Args:
        file_path: Path to the document file

    Returns:
        ParsedDocument: The parsed document with content and metadata

    Raises:
        DocumentNotFoundError: If the file doesn't exist
        UnsupportedDocumentFormatError: If the format is not supported
        DocumentReadError: If the file can't be read
        DocumentParseError: If parsing fails
    """
    logger.info(f"Parsing document: {file_path}")

    try:
        parser = DocumentParserFactory.get_parser(file_path)
        document = parser.parse(file_path)
        logger.info(
            f"Successfully parsed '{file_path}': "
            f"{document.word_count} words, {document.character_count} characters"
        )
        return document

    except DocumentError:
        # Re-raise document errors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing '{file_path}': {e}", exc_info=True)
        raise DocumentParseError(
            str(file_path),
            f"Unexpected error during parsing: {e}"
        )


def write_document(
    file_path: str,
    content: str,
    encoding: str = 'utf-8',
    create_dirs: bool = False,
) -> None:
    """Write content to a document file.

    Args:
        file_path: Path to write the document to
        content: The content to write
        encoding: Character encoding to use (default: utf-8)
        create_dirs: Whether to create parent directories if they don't exist

    Raises:
        DocumentWriteError: If writing fails
    """
    path = Path(file_path)

    # Create parent directories if requested
    if create_dirs:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise DocumentWriteError(
                str(file_path),
                f"Permission denied creating directory: {path.parent}"
            )
        except OSError as e:
            raise DocumentWriteError(
                str(file_path),
                f"Failed to create directory '{path.parent}': {e}"
            )

    # Check if parent directory exists
    if not path.parent.exists():
        raise DocumentWriteError(
            str(file_path),
            f"Parent directory does not exist: {path.parent}. "
            "Use create_dirs=True to create it automatically."
        )

    # Check if path is a directory
    if path.exists() and path.is_dir():
        raise DocumentWriteError(
            str(file_path),
            "Path exists and is a directory, not a file"
        )

    # Write the file
    try:
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        logger.info(f"Successfully wrote {len(content)} characters to '{file_path}'")

    except PermissionError:
        raise DocumentWriteError(
            str(file_path),
            "Permission denied. Check write permissions for the file and directory."
        )
    except UnicodeEncodeError as e:
        raise DocumentWriteError(
            str(file_path),
            f"Could not encode content with {encoding} encoding: {e}"
        )
    except IOError as e:
        raise DocumentWriteError(
            str(file_path),
            f"I/O error while writing file: {e}"
        )
    except OSError as e:
        # Handle disk full, quota exceeded, etc.
        raise DocumentWriteError(
            str(file_path),
            f"OS error while writing file: {e}"
        )

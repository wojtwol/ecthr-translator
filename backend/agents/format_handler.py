"""Format Handler - DOCX parsing and reconstruction."""

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FormatHandler:
    """Handles DOCX format extraction and reconstruction."""

    def extract(self, source_path: str) -> Dict[str, Any]:
        """
        Extract text segments from DOCX while preserving format metadata.

        Args:
            source_path: Path to source DOCX file

        Returns:
            Dictionary with segments and document metadata
        """
        try:
            doc = Document(source_path)
            segments = []

            # Extract paragraphs
            for i, para in enumerate(doc.paragraphs):
                if not para.text.strip():  # Skip empty paragraphs
                    continue

                segment = {
                    "index": i,
                    "text": para.text,
                    "format": self._extract_paragraph_format(para),
                    "parent_type": "paragraph",
                }
                segments.append(segment)

            # Extract tables
            for table_idx, table in enumerate(doc.tables):
                for row_idx, row in enumerate(table.rows):
                    for col_idx, cell in enumerate(row.cells):
                        for para in cell.paragraphs:
                            if not para.text.strip():
                                continue

                            segment = {
                                "index": len(segments),
                                "text": para.text,
                                "format": self._extract_paragraph_format(para),
                                "parent_type": "table_cell",
                                "table_position": {
                                    "table": table_idx,
                                    "row": row_idx,
                                    "col": col_idx,
                                },
                            }
                            segments.append(segment)

            document_metadata = self._extract_document_metadata(doc)

            logger.info(f"Extracted {len(segments)} segments from {source_path}")

            return {
                "segments": segments,
                "document_metadata": document_metadata,
            }

        except Exception as e:
            logger.error(f"Error extracting DOCX: {e}")
            raise

    def reconstruct(
        self,
        translated_segments: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Reconstruct DOCX from translated segments.

        Args:
            translated_segments: List of translated segments with format metadata
            metadata: Document metadata
            output_path: Path to save reconstructed DOCX

        Returns:
            Path to reconstructed DOCX file
        """
        try:
            doc = Document()

            # Apply document-level styles (simplified for Sprint 1)
            # Full style restoration will be in Sprint 2

            # Reconstruct paragraphs
            for segment in translated_segments:
                if segment["parent_type"] == "paragraph":
                    para = doc.add_paragraph()
                    para.text = segment.get("text", "")
                    self._apply_paragraph_format(para, segment.get("format", {}))

            # Save document
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            doc.save(output_path)

            logger.info(f"Reconstructed DOCX saved to {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Error reconstructing DOCX: {e}")
            raise

    def _extract_paragraph_format(self, para) -> Dict[str, Any]:
        """Extract formatting information from a paragraph."""
        format_data = {
            "alignment": str(para.alignment) if para.alignment else None,
            "style": para.style.name if para.style else None,
        }

        # Extract run-level formatting from first run (simplified)
        if para.runs:
            first_run = para.runs[0]
            format_data["font"] = {
                "name": first_run.font.name,
                "size": first_run.font.size.pt if first_run.font.size else None,
                "bold": first_run.font.bold,
                "italic": first_run.font.italic,
                "underline": first_run.font.underline,
            }

        return format_data

    def _apply_paragraph_format(self, para, format_data: Dict[str, Any]) -> None:
        """Apply formatting to a paragraph."""
        # Apply alignment
        if format_data.get("alignment"):
            try:
                para.alignment = eval(format_data["alignment"])
            except:
                pass

        # Apply style
        if format_data.get("style"):
            try:
                para.style = format_data["style"]
            except:
                pass

        # Apply font formatting to runs
        if para.runs and format_data.get("font"):
            font_data = format_data["font"]
            for run in para.runs:
                if font_data.get("name"):
                    run.font.name = font_data["name"]
                if font_data.get("size"):
                    run.font.size = Pt(font_data["size"])
                if font_data.get("bold") is not None:
                    run.font.bold = font_data["bold"]
                if font_data.get("italic") is not None:
                    run.font.italic = font_data["italic"]
                if font_data.get("underline") is not None:
                    run.font.underline = font_data["underline"]

    def _extract_document_metadata(self, doc) -> Dict[str, Any]:
        """Extract document-level metadata."""
        metadata = {
            "core_properties": {
                "title": doc.core_properties.title,
                "author": doc.core_properties.author,
                "subject": doc.core_properties.subject,
            },
            "styles": [style.name for style in doc.styles],
        }
        return metadata

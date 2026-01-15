"""Orchestrator - koordynuje workflow tłumaczenia."""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from agents.format_handler import FormatHandler
from agents.structure_parser import StructureParser
from agents.term_extractor import TermExtractor
from agents.translator import Translator
from agents.change_implementer import ChangeImplementer
from agents.qa_reviewer import QAReviewer
from services.tm_manager import TMManager
from config import settings

logger = logging.getLogger(__name__)


class TranslationResult:
    """Wynik procesu tłumaczenia."""

    def __init__(
        self,
        status: str,
        document_id: str,
        segments: Optional[List[Dict]] = None,
        terms: Optional[List[Dict]] = None,
        translated_path: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.status = status
        self.document_id = document_id
        self.segments = segments or []
        self.terms = terms or []
        self.translated_path = translated_path
        self.error = error


class Orchestrator:
    """Zarządza całym workflow tłumaczenia."""

    def __init__(self):
        """Inicjalizacja Orchestrator."""
        self.format_handler = FormatHandler()
        self.structure_parser = StructureParser()
        self.tm_manager = TMManager()
        self.term_extractor = TermExtractor()
        self.translator = Translator()
        self.change_implementer = ChangeImplementer()
        self.qa_reviewer = QAReviewer()

        # Załaduj TM jeśli istnieje
        try:
            count = self.tm_manager.load()
            logger.info(f"Loaded {count} TM entries")
        except Exception as e:
            logger.warning(f"Could not load TM: {e}")

        logger.info("Orchestrator initialized with Sprint 5 agents")

    async def process(
        self, document_id: str, source_path: str
    ) -> TranslationResult:
        """
        Przetwarza dokument przez cały pipeline.

        Args:
            document_id: ID dokumentu
            source_path: Ścieżka do pliku źródłowego

        Returns:
            TranslationResult
        """
        try:
            logger.info(f"Starting translation for document {document_id}")

            # Faza 1: Ekstrakcja formatów
            logger.info("Phase 1: Extracting document structure")
            extracted = self.format_handler.extract(source_path)
            segments = extracted["segments"]
            document_metadata = extracted["document_metadata"]

            if not segments:
                return TranslationResult(
                    status="error",
                    document_id=document_id,
                    error="No segments extracted from document",
                )

            logger.info(f"Extracted {len(segments)} segments")

            # Faza 2: Analiza struktury
            logger.info("Phase 2: Parsing structure")
            parsed_segments = await self.structure_parser.parse(segments)

            # Faza 3: Ekstrakcja terminów
            logger.info("Phase 3: Extracting terms")

            # Przygotuj znane terminy z TM
            known_terms = []
            for segment in parsed_segments:
                # Spróbuj znaleźć exact match w TM
                tm_match = self.tm_manager.find_exact(segment.get("text", ""))
                if tm_match:
                    known_terms.append(
                        {"source": tm_match.source, "target": tm_match.target}
                    )

            # Ekstrahuj nowe terminy
            extracted_terms = await self.term_extractor.extract(
                parsed_segments, known_terms
            )

            logger.info(f"Extracted {len(extracted_terms)} new terms")

            # Faza 4: Wstępne tłumaczenie (dla demo)
            # W pełnej wersji tutaj czekamy na walidację użytkownika
            logger.info("Phase 4: Generating draft translation")

            # Przygotuj terminologię (połącz TM + nowe terminy)
            terminology = {}

            # Dodaj znane terminy z TM
            for term in known_terms[:50]:  # Ogranicz do 50
                terminology[term["source"]] = term["target"]

            # Dodaj nowe terminy (z proposed_translation)
            for term in extracted_terms[:30]:  # Ogranicz do 30
                terminology[term["source_term"]] = term["proposed_translation"]

            # Tłumacz segmenty
            translated_segments = await self.translator.translate(
                parsed_segments, terminology
            )

            logger.info(
                f"Translation complete. Stats: {self.translator.get_translation_stats(translated_segments)}"
            )

            # Zwróć wynik (bez rekonstrukcji DOCX - to po walidacji)
            return TranslationResult(
                status="awaiting_validation",
                document_id=document_id,
                segments=translated_segments,
                terms=extracted_terms,
            )

        except Exception as e:
            logger.error(f"Error in orchestrator: {e}", exc_info=True)
            return TranslationResult(
                status="error", document_id=document_id, error=str(e)
            )

    async def finalize(
        self,
        document_id: str,
        segments: List[Dict[str, Any]],
        validated_terms: List[Dict[str, Any]],
        original_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Finalizuje tłumaczenie po walidacji użytkownika (Sprint 5).

        Workflow:
        1. Change Implementer - wdraża zatwierdzone zmiany terminów
        2. QA Reviewer - sprawdza spójność i jakość
        3. Rekonstrukcja DOCX
        4. Automatyczny update TM

        Args:
            document_id: ID dokumentu
            segments: Segmenty z tłumaczeniami
            validated_terms: Zatwierdzone terminy
            original_metadata: Metadane oryginalnego dokumentu

        Returns:
            Słownik z wynikiem finalizacji zawierający status, ścieżkę i raport QA
        """
        try:
            logger.info(f"[Sprint 5] Finalizing translation for document {document_id}")

            # Faza 1: Change Implementer - wdróż zmiany terminów
            logger.info("Phase 1: Implementing terminology changes")
            updated_segments = await self.change_implementer.implement_changes(
                segments, validated_terms
            )

            # Faza 2: QA Reviewer - sprawdź jakość
            logger.info("Phase 2: QA review")
            qa_report = await self.qa_reviewer.review(
                updated_segments, validated_terms
            )

            logger.info(
                f"QA Review complete: {qa_report.get('issues_count', {})}"
            )

            # Jeśli QA nie zatwierdza, zwróć raport z ostrzeżeniem
            if not qa_report.get("approved", False):
                logger.warning("QA review found critical issues")
                return {
                    "status": "qa_failed",
                    "document_id": document_id,
                    "qa_report": qa_report,
                    "message": "Translation has quality issues that should be reviewed",
                }

            # Faza 3: Rekonstrukcja DOCX
            logger.info("Phase 3: Reconstructing DOCX")
            output_path = settings.output_path / f"{document_id}_translated.docx"
            self.format_handler.reconstruct(
                updated_segments, original_metadata, str(output_path)
            )

            # Faza 4: Automatyczny update TM
            logger.info("Phase 4: Updating Translation Memory")
            tm_updated_count = 0

            for term in validated_terms:
                if term.get("status") in ["approved", "edited"]:
                    self.tm_manager.add_entry(
                        source=term["source_term"],
                        target=term["target_term"],
                        metadata={
                            "source": "user_validated",
                            "document_id": document_id,
                            "status": term.get("status"),
                        },
                    )
                    tm_updated_count += 1

            # Zapisz zaktualizowaną TM
            tm_filename = f"tm_updated_{document_id}.tmx"
            self.tm_manager.save(tm_filename)

            logger.info(
                f"Translation finalized successfully: {output_path}, "
                f"TM updated with {tm_updated_count} terms"
            )

            return {
                "status": "completed",
                "document_id": document_id,
                "translated_path": str(output_path),
                "qa_report": qa_report,
                "tm_updated": tm_updated_count,
                "tm_file": tm_filename,
            }

        except Exception as e:
            logger.error(f"Error finalizing translation: {e}", exc_info=True)
            return {
                "status": "error",
                "document_id": document_id,
                "error": str(e),
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki Orchestrator.

        Returns:
            Słownik ze statystykami
        """
        stats = {
            "tm_stats": self.tm_manager.get_stats(),
            "agents": {
                "format_handler": "active",
                "structure_parser": "active",
                "term_extractor": "active",
                "translator": "active",
                "change_implementer": self.change_implementer.get_stats(),
                "qa_reviewer": self.qa_reviewer.get_stats(),
            },
        }

        # Dodaj statystyki Case Law Researcher jeśli jest włączony
        if self.term_extractor.enable_case_law_research:
            researcher = self.term_extractor._get_case_law_researcher()
            if researcher:
                stats["case_law_research"] = researcher.get_stats()

        return stats

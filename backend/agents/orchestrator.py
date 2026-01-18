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

    async def process_in_batches(
        self,
        document_id: str,
        source_path: str,
        on_batch_ready=None,
        batch_size: int = 10,
    ):
        """
        Przetwarza dokument w batchach - progresywna ekstrakcja terminów.

        Workflow:
        1. Ekstraktuje i przetwarza BATCH_SIZE segmentów
        2. Wywołuje callback on_batch_ready() z terminami do walidacji
        3. Użytkownik może walidować terminy z batcha 1 podczas gdy system przetwarza batch 2

        Args:
            document_id: ID dokumentu
            source_path: Ścieżka do pliku źródłowego
            on_batch_ready: Callback wywoływany dla każdego batcha: on_batch_ready(terms, segments, is_last, batch_idx, total_batches)
            batch_size: Liczba segmentów w batchu

        Returns:
            TranslationResult z wszystkimi segmentami
        """
        try:
            logger.info(f"Starting BATCH translation for document {document_id} (batch_size={batch_size})")

            # Faza 1: Ekstrakcja formatów
            logger.info("Phase 1: Extracting document structure")
            extracted = self.format_handler.extract(source_path)
            all_segments = extracted["segments"]
            document_metadata = extracted["document_metadata"]

            if not all_segments:
                return TranslationResult(
                    status="error",
                    document_id=document_id,
                    error="No segments extracted from document",
                )

            logger.info(f"Extracted {len(all_segments)} segments, processing in batches of {batch_size}")

            # Faza 2: Analiza struktury wszystkich segmentów
            logger.info("Phase 2: Parsing structure")
            parsed_segments = await self.structure_parser.parse(all_segments)

            # Przygotuj znane terminy z TM
            known_terms = []
            for segment in parsed_segments:
                tm_match = self.tm_manager.find_exact(segment.get("text", ""))
                if tm_match:
                    known_terms.append(
                        {"source": tm_match.source, "target": tm_match.target}
                    )

            # Przygotuj terminologię bazową z TM
            base_terminology = {}
            for term in known_terms[:50]:
                base_terminology[term["source"]] = term["target"]

            # Przetwarzaj segmenty w batchach
            all_translated_segments = []
            all_extracted_terms = []

            num_batches = (len(parsed_segments) + batch_size - 1) // batch_size

            for batch_idx in range(num_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(parsed_segments))
                batch_segments = parsed_segments[start_idx:end_idx]
                is_last_batch = (batch_idx == num_batches - 1)

                logger.info(f"Processing batch {batch_idx + 1}/{num_batches} (segments {start_idx}-{end_idx})")

                # Faza 3: Ekstrakcja terminów dla tego batcha
                batch_terms = await self.term_extractor.extract(batch_segments, known_terms)
                all_extracted_terms.extend(batch_terms)

                logger.info(f"Batch {batch_idx + 1}: Extracted {len(batch_terms)} terms")

                # Przygotuj terminologię dla tego batcha
                batch_terminology = base_terminology.copy()
                for term in batch_terms[:30]:
                    batch_terminology[term["source_term"]] = term["proposed_translation"]

                # Faza 4: Tłumaczenie tego batcha
                translated_batch = await self.translator.translate(
                    batch_segments, batch_terminology
                )
                all_translated_segments.extend(translated_batch)

                logger.info(f"Batch {batch_idx + 1}: Translated {len(translated_batch)} segments")

                # Wywołaj callback z batchem terminów
                if on_batch_ready and batch_terms:
                    try:
                        await on_batch_ready(batch_terms, translated_batch, is_last_batch, batch_idx + 1, num_batches)
                    except Exception as e:
                        logger.error(f"Error in batch callback: {e}", exc_info=True)

            logger.info(
                f"Batch processing complete. Total: {len(all_translated_segments)} segments, "
                f"{len(all_extracted_terms)} terms"
            )

            return TranslationResult(
                status="awaiting_validation",
                document_id=document_id,
                segments=all_translated_segments,
                terms=all_extracted_terms,
            )

        except Exception as e:
            logger.error(f"Error in batch processing: {e}", exc_info=True)
            return TranslationResult(
                status="error", document_id=document_id, error=str(e)
            )

    async def process_quick(
        self, document_id: str, source_path: str, use_hudoc: bool = False, use_curia: bool = False, on_segment_translated=None
    ) -> TranslationResult:
        """
        Quick translation workflow - uses TM + optionally HUDOC/CURIA, without term extraction and validation.

        This mode:
        - Extracts document structure
        - Uses Translation Memory for terminology
        - Optionally enriches with HUDOC/CURIA terminology
        - Translates directly
        - Skips term extraction and user validation
        - Completes immediately with final DOCX

        Args:
            document_id: ID dokumentu
            source_path: Ścieżka do pliku źródłowego
            use_hudoc: Whether to use HUDOC for terminology enrichment
            use_curia: Whether to use CURIA for terminology enrichment

        Returns:
            TranslationResult with completed translation
        """
        try:
            logger.info(f"Starting QUICK translation for document {document_id} (HUDOC: {use_hudoc}, CURIA: {use_curia})")

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

            # Faza 3: Przygotuj terminologię z TM + opcjonalnie HUDOC/CURIA
            logger.info("Phase 3: Loading terminology from TM + optional case law databases")
            terminology = {}

            # Zbierz znane terminy z TM dla każdego segmentu
            for segment in parsed_segments:
                tm_match = self.tm_manager.find_exact(segment.get("text", ""))
                if tm_match:
                    terminology[tm_match.source] = tm_match.target

            logger.info(f"Loaded {len(terminology)} terms from Translation Memory")

            # Opcjonalnie wzbogać terminologię z HUDOC/CURIA
            if use_hudoc or use_curia:
                logger.info("Enriching terminology with case law research (quick mode)")
                try:
                    # Użyj Case Law Researcher do wzbogacenia terminologii
                    case_law_researcher = self.term_extractor._get_case_law_researcher()

                    if case_law_researcher:
                        # Zbierz unikalne terminy z TM jako seed terms
                        seed_terms = list(terminology.keys())[:20]  # Limit do 20 terminów dla szybkości

                        for term in seed_terms:
                            if use_hudoc:
                                hudoc_results = await case_law_researcher.search_hudoc(term)
                                if hudoc_results:
                                    # Dodaj znalezione tłumaczenia do terminologii
                                    for result in hudoc_results[:3]:  # Top 3 wyniki
                                        if 'target' in result:
                                            terminology[result['source']] = result['target']

                            if use_curia:
                                curia_results = await case_law_researcher.search_curia(term)
                                if curia_results:
                                    for result in curia_results[:3]:
                                        if 'target' in result:
                                            terminology[result['source']] = result['target']

                        logger.info(f"Enriched terminology: now {len(terminology)} terms (added from case law)")
                except Exception as e:
                    logger.warning(f"Could not enrich terminology from case law: {e}")
                    # Continue with TM-only terminology

            # Faza 4: Tłumaczenie
            logger.info("Phase 4: Translating with TM terminology")

            # Create translator with callback for live updates
            translator = Translator(on_segment_translated=on_segment_translated)
            translated_segments = await translator.translate(
                parsed_segments, terminology
            )

            logger.info(
                f"Translation complete. Stats: {translator.get_translation_stats(translated_segments)}"
            )

            # Faza 5: Rekonstrukcja DOCX (bez QA review)
            logger.info("Phase 5: Reconstructing DOCX")
            output_path = settings.output_path / f"{document_id}_translated.docx"
            self.format_handler.reconstruct(
                translated_segments, document_metadata, str(output_path)
            )

            # Faza 6: Automatyczny update TM ze wszystkich segmentów
            logger.info("Phase 6: Updating Translation Memory")
            tm_updated_count = 0

            for segment in translated_segments:
                source_text = segment.get("text", "")
                target_text = segment.get("target_text", "")

                if source_text and target_text and not target_text.startswith("["):
                    self.tm_manager.add_entry(
                        source=source_text,
                        target=target_text,
                        metadata={
                            "source": "quick_translation",
                            "document_id": document_id,
                        },
                    )
                    tm_updated_count += 1

            # Zapisz zaktualizowaną TM
            tm_filename = f"tm_updated_{document_id}.tmx"
            self.tm_manager.save(tm_filename)

            logger.info(
                f"Quick translation completed: {output_path}, "
                f"TM updated with {tm_updated_count} segments"
            )

            return TranslationResult(
                status="completed",
                document_id=document_id,
                segments=translated_segments,
                terms=[],  # No terms in quick mode
                translated_path=str(output_path),
            )

        except Exception as e:
            logger.error(f"Error in quick translation: {e}", exc_info=True)
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

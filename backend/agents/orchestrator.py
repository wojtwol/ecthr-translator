"""Orchestrator - koordynuje workflow tłumaczenia."""

import gc
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from agents.format_handler import FormatHandler
from agents.structure_parser import StructureParser
from agents.term_extractor import TermExtractor
from agents.translator import Translator
from agents.change_implementer import ChangeImplementer
from agents.qa_reviewer import QAReviewer
from agents.citation_detector import CitationDetector
from services.multi_tm_manager import MultiTMManager  # New: Multi-TM support
from services.curia_client import CURIAClient
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

    def __init__(self, tm_manager: MultiTMManager = None):
        """Inicjalizacja Orchestrator.

        Args:
            tm_manager: Shared MultiTMManager instance. If None, creates a new one.
        """
        self.format_handler = FormatHandler()
        self.structure_parser = StructureParser()
        self.tm_manager = tm_manager or MultiTMManager()
        self.term_extractor = TermExtractor()
        self.translator = Translator(tm_manager=self.tm_manager)
        self.change_implementer = ChangeImplementer()
        self.qa_reviewer = QAReviewer()
        self.curia_client = CURIAClient()

        # Lazy loading flag for TM
        self._tm_loaded = False

        # Citation detector (optional, controlled by feature flag)
        self.citation_detector = None
        if settings.enable_citation_detection:
            self.citation_detector = CitationDetector()
            logger.info("Citation detection ENABLED (detection-only mode)")

        logger.info("Orchestrator initialized with Multi-TM support + CJEU citation detection (lazy TM loading)")

    def _ensure_tm_loaded(self):
        """Lazy load TM entries on first use to save memory during early phases."""
        if self._tm_loaded:
            return

        try:
            logger.info("Lazy loading Translation Memories...")
            count = self.tm_manager.load_all_from_directory()
            logger.info(f"Loaded {count} TM entries from {len(self.tm_manager.memories)} TM files")

            # Log TM stats
            stats = self.tm_manager.get_stats()
            logger.info(f"TM Stats: {stats['enabled_memories']}/{stats['total_memories']} enabled")
            for tm_info in stats['memories']:
                logger.info(f"  - {tm_info['name']}: priority={tm_info['priority']}, entries={tm_info['entries']}, enabled={tm_info['enabled']}")

            self._tm_loaded = True
        except Exception as e:
            logger.warning(f"Could not load TMs: {e}")

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

            # Lazy load TM before Phase 3 (first use)
            self._ensure_tm_loaded()

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
        ws_manager=None,
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

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "starting", 0.05,
                    "🚀 Rozpoczynam tłumaczenie z walidacją terminów..."
                )

            # Faza 1: Ekstrakcja formatów
            logger.info("Phase 1: Extracting document structure")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "extracting", 0.10,
                    "📄 Analizuję strukturę dokumentu..."
                )

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

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "extracted", 0.15,
                    f"✓ Wyekstrahowano {len(all_segments)} segmentów - przetwarzam w batchach po {batch_size}"
                )

            # Faza 2: Analiza struktury wszystkich segmentów
            logger.info("Phase 2: Parsing structure")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "parsing", 0.20,
                    "🔍 Rozpoznaję strukturę prawną dokumentu..."
                )

            parsed_segments = await self.structure_parser.parse(all_segments)

            # Lazy load TM before using it
            self._ensure_tm_loaded()

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

                # Progress for this batch (30% to 90% spread across all batches)
                batch_progress = 0.30 + (batch_idx / num_batches) * 0.60

                if ws_manager:
                    await ws_manager.broadcast_progress(
                        document_id, "extracting_terms", batch_progress,
                        f"📝 Ekstrahuję terminy prawnicze... (batch {batch_idx + 1}/{num_batches})"
                    )

                # Faza 3: Ekstrakcja terminów dla tego batcha
                batch_terms = await self.term_extractor.extract(batch_segments, known_terms, document_id=document_id, ws_manager=ws_manager, current_progress=batch_progress, all_segments=parsed_segments)
                all_extracted_terms.extend(batch_terms)

                logger.info(f"Batch {batch_idx + 1}: Extracted {len(batch_terms)} terms")

                # Przygotuj terminologię dla tego batcha
                batch_terminology = base_terminology.copy()
                for term in batch_terms[:30]:
                    batch_terminology[term["source_term"]] = term["proposed_translation"]

                # Faza 4: Tłumaczenie tego batcha
                translated_batch = await self.translator.translate(
                    batch_segments, batch_terminology, document_id=document_id, ws_manager=ws_manager
                )
                all_translated_segments.extend(translated_batch)

                logger.info(f"Batch {batch_idx + 1}: Translated {len(translated_batch)} segments")

                # Wywołaj callback z batchem terminów
                # CRITICAL: Always call callback for last batch, even if no terms found
                # Frontend needs is_last=True signal to finalize extraction
                if on_batch_ready and (batch_terms or is_last_batch):
                    try:
                        await on_batch_ready(batch_terms, translated_batch, is_last_batch, batch_idx + 1, num_batches)
                    except Exception as e:
                        logger.error(f"Error in batch callback: {e}", exc_info=True)

                # Free memory after each batch to prevent OOM on limited RAM
                gc.collect()

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
        self, document_id: str, source_path: str, use_hudoc: bool = False, use_curia: bool = False, use_iate: bool = False, on_segment_translated=None, ws_manager=None
    ) -> TranslationResult:
        """
        Quick translation workflow - uses TM + optionally HUDOC/CURIA/IATE, without term extraction and validation.

        This mode:
        - Extracts document structure
        - Uses Translation Memory for terminology
        - Optionally enriches with HUDOC/CURIA/IATE terminology
        - Translates directly
        - Skips term extraction and user validation
        - Completes immediately with final DOCX

        Args:
            document_id: ID dokumentu
            source_path: Ścieżka do pliku źródłowego
            use_hudoc: Whether to use HUDOC for terminology enrichment
            use_curia: Whether to use CURIA for terminology enrichment
            use_iate: Whether to use IATE for terminology enrichment

        Returns:
            TranslationResult with completed translation
        """
        try:
            logger.info(f"Starting QUICK translation for document {document_id} (HUDOC: {use_hudoc}, CURIA: {use_curia}, IATE: {use_iate})")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "starting", 0.05,
                    "🚀 Rozpoczynam szybkie tłumaczenie..."
                )

            # Faza 1: Ekstrakcja formatów
            logger.info("Phase 1: Extracting document structure")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "extracting", 0.10,
                    "📄 Analizuję strukturę dokumentu..."
                )

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

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "extracted", 0.20,
                    f"✓ Wyekstrahowano {len(segments)} segmentów tekstu"
                )

            # Faza 2: Analiza struktury
            logger.info("Phase 2: Parsing structure")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "parsing", 0.25,
                    "🔍 Rozpoznaję strukturę prawną dokumentu..."
                )

            parsed_segments = await self.structure_parser.parse(segments)

            # OPTIONAL: Citation detection (if enabled)
            if self.citation_detector:
                logger.info("Phase 2.5: Detecting case citations (optional feature)")
                try:
                    # Reconstruct source text from segments
                    source_text = "\n".join([seg.get("text", "") for seg in segments])
                    citations = self.citation_detector.detect_citations(source_text)

                    if citations["total"] > 0:
                        summary = self.citation_detector.get_summary(citations)
                        logger.info(summary)
                    else:
                        logger.info("No case citations detected in source text")

                    # Phase 1: Only log results, do not fetch terminology yet
                    # Phase 2 (future): Will fetch terms from cited cases

                except Exception as e:
                    logger.warning(f"Citation detection failed (non-critical): {e}")
                    # Continue with normal flow - this is optional feature

            # Phase 2.5: CJEU Citation Pre-processing
            # Detect CJEU judgments cited in text and add them to TM
            logger.info("Phase 2.5: Detecting CJEU citations and fetching judgments")

            try:
                # Concatenate all segments to search for citations
                full_text = " ".join([seg.get("text", "") for seg in parsed_segments])

                # Detect CJEU citations (C-xxx/xx format)
                cjeu_citations = self.curia_client.detect_cjeu_citations(full_text)

                if cjeu_citations:
                    logger.info(f"Found {len(cjeu_citations)} CJEU citations in document")

                    if ws_manager:
                        await ws_manager.broadcast_progress(
                            document_id, "detecting_cjeu_citations", 0.25,
                            f"⚖️ Wykryto {len(cjeu_citations)} cytatów z wyroków TSUE"
                        )

                    # For each citation, fetch the judgment and add to TM
                    for idx, citation in enumerate(cjeu_citations):
                        case_number = citation["case_number"]
                        logger.info(f"Processing CJEU citation: {case_number}")

                        if ws_manager:
                            await ws_manager.broadcast_progress(
                                document_id, "fetching_cjeu_judgment", 0.25 + (idx / len(cjeu_citations)) * 0.05,
                                f"📥 Pobieram wyrok TSUE {case_number}..."
                            )

                        # Fetch judgment from CURIA with paragraph extraction
                        judgment = await self.curia_client.get_judgment_by_case_number(
                            case_number=case_number,
                            source_lang="EN",
                            target_lang="PL"
                        )

                        if judgment and judgment.get("available"):
                            paragraphs = judgment.get("paragraphs", {})

                            if paragraphs:
                                logger.info(f"Successfully fetched {len(paragraphs)} paragraphs from CJEU judgment {case_number}")

                                # Add each paragraph to Translation Memory with HIGHEST priority
                                # CJEU official translations have confidence 1.0 (same as exact TM match)
                                for para_num, para_data in paragraphs.items():
                                    text_en = para_data.get("en", "")
                                    text_pl = para_data.get("pl", "")

                                    if text_en and text_pl:
                                        self.tm_manager.add_entry(
                                            source=text_en,
                                            target=text_pl,
                                            metadata={
                                                "source": "curia_citation",
                                                "case_number": case_number,
                                                "paragraph": para_num,
                                                "confidence": 1.0,
                                            }
                                        )

                                logger.info(f"Added {len(paragraphs)} CJEU paragraphs to TM with priority 1.0")

                                if ws_manager:
                                    await ws_manager.broadcast_progress(
                                        document_id, "cjeu_tm_updated", 0.28 + (idx / len(cjeu_citations)) * 0.02,
                                        f"✓ Dodano {len(paragraphs)} paragrafów z wyroku {case_number} do TM"
                                    )
                            else:
                                logger.warning(f"No paragraphs extracted from CJEU judgment {case_number}")
                        else:
                            logger.warning(f"Could not fetch CJEU judgment {case_number}")

                    if ws_manager:
                        await ws_manager.broadcast_progress(
                            document_id, "cjeu_processing_complete", 0.30,
                            f"✓ Przetworzono {len(cjeu_citations)} cytatów TSUE"
                        )
                else:
                    logger.info("No CJEU citations detected in document")

            except Exception as e:
                logger.warning(f"CJEU citation processing failed (non-critical): {e}")
                # Continue with normal flow

            # Lazy load TM before Phase 3
            self._ensure_tm_loaded()

            # Faza 3: Przygotuj terminologię z TM + opcjonalnie HUDOC/CURIA
            logger.info("Phase 3: Loading terminology from TM + optional case law databases")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "loading_terminology", 0.30,
                    "📚 Wczytuję pamięć tłumaczeniową..."
                )

            terminology = {}

            # Zbierz znane terminy z TM dla każdego segmentu
            for segment in parsed_segments:
                tm_match = self.tm_manager.find_exact(segment.get("text", ""))
                if tm_match:
                    terminology[tm_match.source] = tm_match.target

            logger.info(f"Loaded {len(terminology)} terms from Translation Memory")

            if ws_manager:
                await ws_manager.broadcast_progress(
                    document_id, "loading_tm", 0.35,
                    f"✓ Wczytano {len(terminology)} terminów z pamięci tłumaczeniowej"
                )

            # Opcjonalnie wzbogać terminologię z HUDOC/CURIA/IATE
            if use_hudoc or use_curia or use_iate:
                databases = []
                if use_hudoc: databases.append("HUDOC")
                if use_curia: databases.append("CURIA")
                if use_iate: databases.append("IATE")

                if ws_manager:
                    await ws_manager.broadcast_progress(
                        document_id, "enriching", 0.40,
                        f"🔍 Wzbogacam terminologię z baz: {', '.join(databases)}..."
                    )

                logger.info("Enriching terminology with case law research (quick mode)")
                try:
                    # Użyj Case Law Researcher do wzbogacenia terminologii
                    case_law_researcher = self.term_extractor._get_case_law_researcher()

                    if case_law_researcher:
                        # Zbierz unikalne terminy z TM jako seed terms
                        seed_terms = list(terminology.keys())[:20]  # Limit do 20 terminów dla szybkości

                        for idx, term in enumerate(seed_terms):
                            if use_hudoc:
                                if ws_manager:
                                    await ws_manager.broadcast_progress(
                                        document_id, "searching_hudoc", 0.40 + (idx / len(seed_terms)) * 0.1,
                                        f"⚖️ Przeszukuję HUDOC dla terminów... ({idx+1}/{len(seed_terms)})"
                                    )
                                hudoc_results = await case_law_researcher.search_term(term, source="hudoc")
                                if hudoc_results:
                                    # Dodaj znalezione tłumaczenia do terminologii
                                    for result in hudoc_results[:3]:  # Top 3 wyniki
                                        if 'term_pl' in result and result['term_pl']:
                                            terminology[result.get('term_en', term)] = result['term_pl']

                            if use_curia:
                                if ws_manager:
                                    await ws_manager.broadcast_progress(
                                        document_id, "searching_curia", 0.50 + (idx / len(seed_terms)) * 0.1,
                                        f"🏛️ Przeszukuję CURIA dla terminów... ({idx+1}/{len(seed_terms)})"
                                    )
                                curia_results = await case_law_researcher.search_term(term, source="curia")
                                if curia_results:
                                    for result in curia_results[:3]:
                                        if 'term_pl' in result and result['term_pl']:
                                            terminology[result.get('term_en', term)] = result['term_pl']

                            if use_iate:
                                if ws_manager:
                                    await ws_manager.broadcast_progress(
                                        document_id, "searching_iate", 0.60 + (idx / len(seed_terms)) * 0.1,
                                        f"🇪🇺 Przeszukuję IATE dla terminów... ({idx+1}/{len(seed_terms)})"
                                    )
                                iate_results = await case_law_researcher.search_term(term, source="iate")
                                if iate_results:
                                    for result in iate_results[:3]:
                                        if 'term_pl' in result and result['term_pl']:
                                            terminology[result.get('term_en', term)] = result['term_pl']

                        logger.info(f"Enriched terminology: now {len(terminology)} terms (added from case law databases)")

                        if ws_manager:
                            await ws_manager.broadcast_progress(
                                document_id, "enriched", 0.70,
                                f"✓ Wzbogacono terminologię: {len(terminology)} terminów gotowych do tłumaczenia"
                            )
                except Exception as e:
                    logger.warning(f"Could not enrich terminology from case law: {e}")
                    # Continue with TM-only terminology

            # Free memory before heavy translation phase
            gc.collect()

            # Faza 4: Tłumaczenie
            logger.info("Phase 4: Translating with TM terminology")

            # Create translator with TM support and callback for live updates
            translator = Translator(tm_manager=self.tm_manager, on_segment_translated=on_segment_translated)
            translated_segments = await translator.translate(
                parsed_segments, terminology
            )

            logger.info(
                f"Translation complete. Stats: {translator.get_translation_stats(translated_segments)}"
            )

            # Free memory before DOCX reconstruction
            gc.collect()

            # Faza 5: Rekonstrukcja DOCX (bez QA review)
            logger.info("Phase 5: Reconstructing DOCX")
            output_path = settings.output_path / f"{document_id}_translated.docx"
            self.format_handler.reconstruct(
                translated_segments,
                document_metadata,
                str(output_path),
                color_citations=settings.color_citations_in_docx
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
            self.tm_manager.save_tm("default", tm_filename)

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

            # Free memory after phase 1
            gc.collect()

            # Faza 2: QA Reviewer - sprawdź jakość
            logger.info("Phase 2: QA review")
            qa_report = await self.qa_reviewer.review(
                updated_segments, validated_terms
            )

            logger.info(
                f"QA Review complete: {qa_report.get('issues_count', {})}"
            )

            # QA issues are informational - log but proceed with finalization
            if not qa_report.get("approved", False):
                logger.warning("QA review found critical issues")

            # Free memory after phase 2
            gc.collect()

            # Faza 3: Rekonstrukcja DOCX
            logger.info("Phase 3: Reconstructing DOCX")
            output_path = settings.output_path / f"{document_id}_translated.docx"
            self.format_handler.reconstruct(
                updated_segments,
                original_metadata,
                str(output_path),
                color_citations=settings.color_citations_in_docx
            )

            # Free memory after phase 3
            gc.collect()

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
            self.tm_manager.save_tm("default", tm_filename)

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
        # Ensure TM is loaded before getting stats
        self._ensure_tm_loaded()

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

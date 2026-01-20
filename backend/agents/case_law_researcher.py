"""Case Law Researcher - przeszukuje źródła orzecznictwa dla terminologii."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from services.hudoc_client import HUDOCClient
from services.curia_client import CURIAClient
from services.iate_client import IATEClient
from services.tm_manager import TMManager

logger = logging.getLogger(__name__)


class CaseLawResearcher:
    """
    Agent przeszukujący TM i bazy orzeczeń (HUDOC, CURIA, IATE) dla terminologii prawniczej.

    Odpowiedzialny za:
    - Wyszukiwanie terminów NAJPIERW w pamięci tłumaczeniowej (TM)
    - Jeśli brak w TM: wyszukiwanie w bazach HUDOC, CURIA i IATE
    - Wzbogacanie terminów o oficjalne tłumaczenia
    - Priorytetyzację wyników na podstawie źródła i pewności
      (TM > HUDOC > CURIA > IATE)
    """

    def __init__(self):
        """Inicjalizacja Case Law Researcher."""
        # Initialize TM Manager FIRST - highest priority source
        self.tm_manager = TMManager()
        try:
            tm_count = self.tm_manager.load()
            logger.info(f"Loaded {tm_count} entries from Translation Memory")
        except Exception as e:
            logger.warning(f"Failed to load TM: {e}. Continuing without TM.")

        # Initialize database clients
        self.hudoc_client = HUDOCClient()
        self.curia_client = CURIAClient()
        self.iate_client = IATEClient()
        logger.info("Case Law Researcher initialized with TM, HUDOC, CURIA, and IATE")

    async def enrich_terms(
        self, terms: List[Dict[str, Any]], document_id: Optional[str] = None, ws_manager = None, current_progress: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Wzbogaca terminy o wyniki z baz orzeczeń.

        Args:
            terms: Lista terminów do wzbogacenia
                   [{"source_term": "margin of appreciation", ...}, ...]

        Returns:
            Lista wzbogaconych terminów z referencjami do orzeczeń
        """
        if not terms:
            logger.info("No terms to enrich")
            return []

        logger.info(f"Enriching {len(terms)} terms with case law research")

        enriched_terms = []
        for idx, term in enumerate(terms):
            source_term = term.get("source_term", "")
            if not source_term:
                enriched_terms.append(term)
                continue

            # Send progress update for each term
            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_databases", current_progress,
                    f"🌐 Przeszukuję HUDOC, CURIA i IATE dla terminu '{source_term}' ({idx + 1}/{len(terms)})..."
                )

            # Wzbogać termin o wyniki z baz orzeczeń
            enriched_term = await self._enrich_single_term(source_term, term, document_id=document_id, ws_manager=ws_manager, current_progress=current_progress)
            enriched_terms.append(enriched_term)

        logger.info(f"Enriched {len(enriched_terms)} terms")
        return enriched_terms

    async def _enrich_single_term(
        self, source_term: str, original_term: Dict[str, Any], document_id: Optional[str] = None, ws_manager = None, current_progress: float = 0.5
    ) -> Dict[str, Any]:
        """
        Wzbogaca pojedynczy termin o wyniki z TM, HUDOC, CURIA i IATE.

        NOWA LOGIKA: Zwraca WSZYSTKIE opcje tłumaczeń, nie wybiera najlepszego.
        Użytkownik widzi wszystkie źródła i sam wybiera.

        KOLEJNOŚĆ WYSZUKIWANIA:
        1. Translation Memory (TM) - zatwierdzone tłumaczenia
        2. HUDOC - orzecznictwo ETPCz
        3. CURIA - orzecznictwo TSUE
        4. IATE - terminologia UE
        5. AI Proposal - propozycja z LLM (już w original_term)

        Args:
            source_term: Termin angielski
            original_term: Oryginalny słownik terminu (zawiera proposed_translation z AI)
            document_id: ID dokumentu (do progress updates)
            ws_manager: WebSocket manager (do progress updates)

        Returns:
            Wzbogacony słownik terminu ze WSZYSTKIMI opcjami tłumaczeń
        """
        try:
            enriched = original_term.copy()
            all_translation_options = []  # Lista wszystkich opcji tłumaczeń
            all_references = []  # Lista wszystkich referencji do case law

            # STEP 1: Check Translation Memory
            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_tm", current_progress,
                    f"   💾 Sprawdzam pamięć tłumaczeniową dla '{source_term}'..."
                )

            tm_entry = self.tm_manager.find_exact(source_term)
            if tm_entry:
                logger.info(f"Found exact TM match for '{source_term}': {tm_entry.target}")
                if ws_manager and document_id:
                    await ws_manager.broadcast_progress(
                        document_id, "tm_found", current_progress,
                        f"   ✓ TM: znaleziono zatwierdzone tłumaczenie!"
                    )

                # Dodaj opcję TM do listy
                all_translation_options.append({
                    "source_type": "tm_exact",  # FIX: było "tm", teraz "tm_exact"
                    "term_pl": tm_entry.target,
                    "confidence": 1.0,
                    "metadata": tm_entry.metadata,
                })

                # Dodaj referencję TM
                all_references.append({
                    "source": "tm_exact",  # FIX: było "tm"
                    "term_en": source_term,
                    "term_pl": tm_entry.target,
                    "confidence": 1.0,
                    "context": original_term.get("context", ""),  # FIX: Dodaj context
                    "metadata": tm_entry.metadata,
                })
            else:
                if ws_manager and document_id:
                    await ws_manager.broadcast_progress(
                        document_id, "tm_not_found", current_progress,
                        f"   ⊘ TM: brak w pamięci, przeszukuję bazy danych..."
                    )

            # STEP 2: Search databases (HUDOC, CURIA, IATE) - zawsze, nawet jeśli TM znaleziono
            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_databases", current_progress,
                    f"   📚 Przeszukuję HUDOC, CURIA i IATE dla '{source_term}'..."
                )

            # Przeszukaj wszystkie trzy źródła równolegle
            hudoc_results, curia_results, iate_results = await asyncio.gather(
                self.hudoc_client.search_term(source_term, max_results=3),
                self.curia_client.search_term(source_term, max_results=3),
                self.iate_client.search_term(source_term, max_results=3),
                return_exceptions=True,
            )

            # Obsłuż błędy
            if isinstance(hudoc_results, Exception):
                logger.error(f"HUDOC search error: {hudoc_results}")
                hudoc_results = []
            elif ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "hudoc_done", current_progress,
                    f"   ✓ HUDOC: znaleziono {len(hudoc_results)} wyników"
                )

            if isinstance(curia_results, Exception):
                logger.error(f"CURIA search error: {curia_results}")
                curia_results = []
            elif ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "curia_done", current_progress,
                    f"   ✓ CURIA: znaleziono {len(curia_results)} wyników"
                )

            if isinstance(iate_results, Exception):
                logger.error(f"IATE search error: {iate_results}")
                iate_results = []
            elif ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "iate_done", current_progress,
                    f"   ✓ IATE: znaleziono {len(iate_results)} wyników"
                )

            # STEP 3: Dodaj wyniki HUDOC do opcji i referencji
            for result in hudoc_results:
                # Dodaj do opcji tłumaczeń
                all_translation_options.append({
                    "source_type": "hudoc",  # FIX: ustawiamy source_type
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "cases": result.get("cases", []),
                    "url": result.get("url"),
                })

                # Dodaj do referencji (dla compatibility)
                all_references.append({
                    "source": "hudoc",
                    "term_en": result.get("term_en"),
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "cases": result.get("cases", []),
                    "url": result.get("url"),
                    "context": original_term.get("context", ""),  # FIX: Dodaj context
                    # FIX: Usunięto "priority" - to pole wewnętrzne, nie powinno być w BD
                })

            # STEP 4: Dodaj wyniki CURIA do opcji i referencji
            for result in curia_results:
                # Dodaj do opcji tłumaczeń
                all_translation_options.append({
                    "source_type": "curia",  # FIX: ustawiamy source_type
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "url": result.get("url"),
                })

                # Dodaj do referencji
                all_references.append({
                    "source": "curia",
                    "term_en": result.get("term_en"),
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "url": result.get("url"),
                    "context": original_term.get("context", ""),  # FIX: Dodaj context
                })

            # STEP 5: Dodaj wyniki IATE do opcji i referencji
            for result in iate_results:
                # Dodaj do opcji tłumaczeń
                all_translation_options.append({
                    "source_type": "iate",  # FIX: ustawiamy source_type
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "url": result.get("url"),
                    "iate_ids": result.get("iate_ids", []),
                    "domain": result.get("domain"),
                })

                # Dodaj do referencji
                all_references.append({
                    "source": "iate",
                    "term_en": result.get("term_en"),
                    "term_pl": result.get("term_pl"),
                    "confidence": result.get("confidence", 0.0),
                    "url": result.get("url"),
                    "context": original_term.get("context", ""),  # FIX: Dodaj context
                    "iate_ids": result.get("iate_ids", []),
                    "domain": result.get("domain"),
                })

            # STEP 6: Dodaj AI proposal do opcji tłumaczeń (zawsze na końcu)
            if original_term.get("proposed_translation"):
                all_translation_options.append({
                    "source_type": "proposed",  # AI proposal
                    "term_pl": original_term.get("proposed_translation"),
                    "confidence": original_term.get("confidence", 0.6),
                    "term_type": original_term.get("term_type", "other"),
                })

            # Zwróć wzbogacony termin ze WSZYSTKIMI opcjami
            enriched["translation_options"] = all_translation_options  # NOWE POLE
            enriched["case_law_references"] = all_references
            enriched["reference_count"] = len(all_references)
            enriched["options_count"] = len(all_translation_options)  # NOWE POLE

            logger.info(
                f"Enriched term '{source_term}' with {len(all_translation_options)} translation options "
                f"from {len(all_references)} references"
            )
            return enriched

        except Exception as e:
            logger.error(f"Error enriching term '{source_term}': {e}")
            return original_term

    def _select_best_translation(
        self,
        source_term: str,
        references: List[Dict[str, Any]],
        proposed_translation: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Wybiera najlepsze tłumaczenie z dostępnych referencji.

        Args:
            source_term: Termin angielski
            references: Lista referencji z tłumaczeniami
            proposed_translation: Propozycja tłumaczenia z LLM

        Returns:
            Najlepsza referencja lub None
        """
        if not references:
            return None

        # Sortuj według priorytetu (HUDOC > CURIA) i pewności
        sorted_refs = sorted(
            references,
            key=lambda x: (x["priority"], -x["confidence"]),
        )

        # Wybierz pierwszą (najlepszą)
        best_ref = sorted_refs[0]

        # Jeśli confidence jest bardzo niskie, zwróć None
        if best_ref["confidence"] < 0.5:
            return None

        return best_ref

    async def search_term(
        self, term: str, source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Wyszukuje termin w określonym źródle lub we wszystkich.

        Args:
            term: Termin do wyszukania
            source: Źródło ("hudoc", "curia", "iate" lub None dla wszystkich)

        Returns:
            Lista wyników
        """
        try:
            if source == "hudoc":
                return await self.hudoc_client.search_term(term)
            elif source == "curia":
                return await self.curia_client.search_term(term)
            elif source == "iate":
                return await self.iate_client.search_term(term)
            else:
                # Przeszukaj wszystkie trzy źródła
                hudoc_results, curia_results, iate_results = await asyncio.gather(
                    self.hudoc_client.search_term(term),
                    self.curia_client.search_term(term),
                    self.iate_client.search_term(term),
                    return_exceptions=True,
                )

                results = []
                if not isinstance(hudoc_results, Exception):
                    results.extend(hudoc_results)
                if not isinstance(curia_results, Exception):
                    results.extend(curia_results)
                if not isinstance(iate_results, Exception):
                    results.extend(iate_results)

                return results

        except Exception as e:
            logger.error(f"Error searching term '{term}': {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki Case Law Researcher.

        Returns:
            Słownik ze statystykami
        """
        return {
            "hudoc": self.hudoc_client.get_stats(),
            "curia": self.curia_client.get_stats(),
            "iate": self.iate_client.get_stats(),
        }

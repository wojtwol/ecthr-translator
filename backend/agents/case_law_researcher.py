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
        self,
        terms: List[Dict[str, Any]],
        document_id: Optional[str] = None,
        ws_manager = None,
        current_progress: float = 0.5,
        on_term_ready = None
    ) -> List[Dict[str, Any]]:
        """
        Wzbogaca terminy o wyniki z baz orzeczeń.

        Args:
            terms: Lista terminów do wzbogacenia
                   [{"source_term": "margin of appreciation", ...}, ...]
            on_term_ready: Optional callback wywoływany dla każdego wzbogaconego terminu
                          on_term_ready(enriched_term) - umożliwia progresywne wyświetlanie

        Returns:
            Lista wzbogaconych terminów z referencjami do orzeczeń
        """
        if not terms:
            logger.info("No terms to enrich")
            return []

        logger.info(f"Enriching {len(terms)} terms with case law research (progressive: {on_term_ready is not None})")

        enriched_terms = []
        for idx, term in enumerate(terms):
            source_term = term.get("source_term", "")
            if not source_term:
                enriched_terms.append(term)
                # Call callback even for non-enriched terms
                if on_term_ready:
                    try:
                        await on_term_ready(term)
                    except Exception as e:
                        logger.error(f"Error in term callback: {e}")
                continue

            # Send progress update for each term
            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_databases", current_progress,
                    f"🌐 Przeszukuję TM/HUDOC/CURIA/IATE dla '{source_term}' ({idx + 1}/{len(terms)})..."
                )

            # Wzbogać termin o wyniki z baz orzeczeń
            enriched_term = await self._enrich_single_term(source_term, term, document_id=document_id, ws_manager=ws_manager, current_progress=current_progress)
            enriched_terms.append(enriched_term)

            # CRITICAL: Call callback IMMEDIATELY after enriching each term
            # This allows frontend to display terms progressively as they're enriched
            if on_term_ready:
                try:
                    await on_term_ready(enriched_term)
                    logger.debug(f"Sent enriched term '{source_term}' to frontend via callback")
                except Exception as e:
                    logger.error(f"Error in term callback for '{source_term}': {e}")

        logger.info(f"Enriched {len(enriched_terms)} terms")
        return enriched_terms

    async def _enrich_single_term(
        self, source_term: str, original_term: Dict[str, Any], document_id: Optional[str] = None, ws_manager = None, current_progress: float = 0.5
    ) -> Dict[str, Any]:
        """
        Wzbogaca pojedynczy termin o wyniki z TM, HUDOC, CURIA i IATE.

        PRIORITY ORDER:
        1. Translation Memory (TM) - najwyższy priorytet, tłumaczenie już zatwierdzone
        2. HUDOC - orzecznictwo ETPCz
        3. CURIA - orzecznictwo TSUE
        4. IATE - terminologia UE

        Args:
            source_term: Termin angielski
            original_term: Oryginalny słownik terminu
            document_id: ID dokumentu (do progress updates)
            ws_manager: WebSocket manager (do progress updates)

        Returns:
            Wzbogacony słownik terminu
        """
        try:
            # STEP 1: Check Translation Memory FIRST (highest priority)
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

                # Return term enriched with TM translation (highest confidence)
                enriched = original_term.copy()
                enriched["official_translation"] = tm_entry.target
                enriched["translation_source"] = "tm"
                enriched["source_type"] = "tm"
                enriched["translation_confidence"] = 1.0  # Perfect confidence for TM
                enriched["case_law_references"] = [
                    {
                        "source": "tm",
                        "term_en": source_term,
                        "term_pl": tm_entry.target,
                        "confidence": 1.0,
                        "metadata": tm_entry.metadata,
                    }
                ]
                enriched["reference_count"] = 1
                logger.info(f"Using TM translation for '{source_term}'")
                return enriched

            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "tm_not_found", current_progress,
                    f"   ⊘ TM: brak w pamięci, przeszukuję bazy danych..."
                )

            # STEP 2: If not in TM, search databases (HUDOC, CURIA, IATE)
            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_hudoc", current_progress,
                    f"   📚 Przeszukuję bazę HUDOC dla '{source_term}'..."
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

            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_curia", current_progress,
                    f"   📚 Przeszukuję bazę CURIA dla '{source_term}'..."
                )

            if isinstance(curia_results, Exception):
                logger.error(f"CURIA search error: {curia_results}")
                curia_results = []
            elif ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "curia_done", current_progress,
                    f"   ✓ CURIA: znaleziono {len(curia_results)} wyników"
                )

            if ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "searching_iate", current_progress,
                    f"   📚 Przeszukuję bazę IATE dla '{source_term}'..."
                )

            if isinstance(iate_results, Exception):
                logger.error(f"IATE search error: {iate_results}")
                iate_results = []
            elif ws_manager and document_id:
                await ws_manager.broadcast_progress(
                    document_id, "iate_done", current_progress,
                    f"   ✓ IATE: znaleziono {len(iate_results)} wyników"
                )

            # Połącz wyniki
            all_references = []

            # Dodaj wyniki HUDOC (priorytet 1 - główne źródło dla ETPCz)
            for result in hudoc_results:
                all_references.append(
                    {
                        "source": "hudoc",
                        "term_en": result.get("term_en"),
                        "term_pl": result.get("term_pl"),
                        "confidence": result.get("confidence", 0.0),
                        "cases": result.get("cases", []),
                        "url": result.get("url"),
                        "priority": 1,  # HUDOC ma najwyższy priorytet dla ETPCz
                    }
                )

            # Dodaj wyniki CURIA (priorytet 2 - pomocnicze źródło)
            for result in curia_results:
                all_references.append(
                    {
                        "source": "curia",
                        "term_en": result.get("term_en"),
                        "term_pl": result.get("term_pl"),
                        "confidence": result.get("confidence", 0.0),
                        "url": result.get("url"),
                        "priority": 2,  # Niższy priorytet dla CURIA
                    }
                )

            # Dodaj wyniki IATE (priorytet 3 - terminologia ogólna UE)
            for result in iate_results:
                all_references.append(
                    {
                        "source": "iate",
                        "term_en": result.get("term_en"),
                        "term_pl": result.get("term_pl"),
                        "confidence": result.get("confidence", 0.0),
                        "url": result.get("url"),
                        "priority": 3,  # Najniższy priorytet - terminologia ogólna
                    }
                )

            # Wybierz najlepsze tłumaczenie
            best_translation = self._select_best_translation(
                source_term, all_references, original_term.get("proposed_translation")
            )

            # Utwórz wzbogacony termin
            enriched_term = original_term.copy()
            enriched_term["case_law_references"] = all_references
            enriched_term["reference_count"] = len(all_references)

            # Jeśli znaleziono lepsze tłumaczenie, zaktualizuj
            if best_translation:
                enriched_term["official_translation"] = best_translation["term_pl"]
                enriched_term["translation_source"] = best_translation["source"]
                enriched_term["translation_confidence"] = best_translation["confidence"]

                # Jeśli tłumaczenie z baz jest inne niż propozycja, dodaj flagę
                if best_translation["term_pl"] != original_term.get(
                    "proposed_translation"
                ):
                    enriched_term["has_alternative"] = True
                    enriched_term["alternative_explanation"] = (
                        f"Oficjalne tłumaczenie z {best_translation['source'].upper()}"
                    )

            logger.debug(
                f"Enriched term '{source_term}' with {len(all_references)} references"
            )
            return enriched_term

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

"""Case Law Researcher - przeszukuje źródła orzecznictwa dla terminologii."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from services.hudoc_client import HUDOCClient
from services.curia_client import CURIAClient

logger = logging.getLogger(__name__)


class CaseLawResearcher:
    """
    Agent przeszukujący bazy orzeczeń (HUDOC, CURIA) dla terminologii prawniczej.

    Odpowiedzialny za:
    - Wyszukiwanie terminów w bazach HUDOC i CURIA
    - Wzbogacanie terminów o oficjalne tłumaczenia
    - Priorytetyzację wyników na podstawie źródła i pewności
    """

    def __init__(self):
        """Inicjalizacja Case Law Researcher."""
        self.hudoc_client = HUDOCClient()
        self.curia_client = CURIAClient()
        logger.info("Case Law Researcher initialized")

    async def enrich_terms(
        self, terms: List[Dict[str, Any]]
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
        for term in terms:
            source_term = term.get("source_term", "")
            if not source_term:
                enriched_terms.append(term)
                continue

            # Wzbogać termin o wyniki z baz orzeczeń
            enriched_term = await self._enrich_single_term(source_term, term)
            enriched_terms.append(enriched_term)

        logger.info(f"Enriched {len(enriched_terms)} terms")
        return enriched_terms

    async def _enrich_single_term(
        self, source_term: str, original_term: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Wzbogaca pojedynczy termin o wyniki z HUDOC i CURIA.

        Args:
            source_term: Termin angielski
            original_term: Oryginalny słownik terminu

        Returns:
            Wzbogacony słownik terminu
        """
        try:
            # Przeszukaj oba źródła równolegle
            hudoc_results, curia_results = await asyncio.gather(
                self.hudoc_client.search_term(source_term, max_results=3),
                self.curia_client.search_term(source_term, max_results=3),
                return_exceptions=True,
            )

            # Obsłuż błędy
            if isinstance(hudoc_results, Exception):
                logger.error(f"HUDOC search error: {hudoc_results}")
                hudoc_results = []

            if isinstance(curia_results, Exception):
                logger.error(f"CURIA search error: {curia_results}")
                curia_results = []

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
            source: Źródło ("hudoc", "curia" lub None dla wszystkich)

        Returns:
            Lista wyników
        """
        try:
            if source == "hudoc":
                return await self.hudoc_client.search_term(term)
            elif source == "curia":
                return await self.curia_client.search_term(term)
            else:
                # Przeszukaj oba źródła
                hudoc_results, curia_results = await asyncio.gather(
                    self.hudoc_client.search_term(term),
                    self.curia_client.search_term(term),
                    return_exceptions=True,
                )

                results = []
                if not isinstance(hudoc_results, Exception):
                    results.extend(hudoc_results)
                if not isinstance(curia_results, Exception):
                    results.extend(curia_results)

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
        }

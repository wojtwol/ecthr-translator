"""
Case Law Researcher Agent.
Coordinates terminology searches across HUDOC, CURIA, and IATE databases.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from loguru import logger

from backend.services.hudoc_client import HUDOCClient
from backend.services.curia_client import CURIAClient
from backend.services.iate_client import IATEClient
from backend.config import settings


@dataclass
class TerminologyResult:
    """Result of terminology search from a single source."""
    term: str
    translation: Optional[str]
    confidence: float
    source: str  # "hudoc", "curia", or "iate"
    references: List[str]
    domain: Optional[str] = None


@dataclass
class EnrichedTerm:
    """Enriched term with results from multiple sources."""
    term: str
    best_translation: Optional[str]
    best_confidence: float
    best_source: Optional[str]
    all_results: List[TerminologyResult]


class CaseLawResearcher:
    """Agent for researching legal terminology across multiple databases."""

    def __init__(self):
        self.hudoc_client = HUDOCClient() if settings.hudoc_enabled else None
        self.curia_client = CURIAClient() if settings.curia_enabled else None
        self.iate_client = IATEClient() if settings.iate_enabled else None

        logger.info(
            f"CaseLawResearcher initialized with: "
            f"HUDOC={settings.hudoc_enabled}, "
            f"CURIA={settings.curia_enabled}, "
            f"IATE={settings.iate_enabled}"
        )

    async def search_term(
        self,
        term: str,
        source_lang: str = "en",
        target_lang: str = "pl",
        sources: Optional[List[str]] = None
    ) -> EnrichedTerm:
        """
        Search for a term across all enabled databases.

        Args:
            term: The term to search for
            source_lang: Source language code
            target_lang: Target language code
            sources: Optional list of sources to search ["hudoc", "curia", "iate"]
                    If None, searches all enabled sources

        Returns:
            EnrichedTerm with results from all sources
        """
        if sources is None:
            sources = []
            if settings.hudoc_enabled:
                sources.append("hudoc")
            if settings.curia_enabled:
                sources.append("curia")
            if settings.iate_enabled:
                sources.append("iate")

        logger.info(f"Searching term '{term}' in sources: {sources}")

        all_results = []

        # Search HUDOC
        if "hudoc" in sources and self.hudoc_client:
            try:
                translation, confidence, refs = await self.hudoc_client.search_term(
                    term, source_lang, target_lang
                )
                all_results.append(TerminologyResult(
                    term=term,
                    translation=translation,
                    confidence=confidence,
                    source="hudoc",
                    references=refs
                ))
            except Exception as e:
                logger.error(f"HUDOC search failed for '{term}': {e}")

        # Search CURIA
        if "curia" in sources and self.curia_client:
            try:
                translation, confidence, refs = await self.curia_client.search_term(
                    term, source_lang, target_lang
                )
                all_results.append(TerminologyResult(
                    term=term,
                    translation=translation,
                    confidence=confidence,
                    source="curia",
                    references=refs
                ))
            except Exception as e:
                logger.error(f"CURIA search failed for '{term}': {e}")

        # Search IATE
        if "iate" in sources and self.iate_client:
            try:
                translation, confidence, refs, domain = await self.iate_client.search_term(
                    term, source_lang, target_lang
                )
                all_results.append(TerminologyResult(
                    term=term,
                    translation=translation,
                    confidence=confidence,
                    source="iate",
                    references=refs,
                    domain=domain
                ))
            except Exception as e:
                logger.error(f"IATE search failed for '{term}': {e}")

        # Find best result
        best_result = self._select_best_result(all_results)

        return EnrichedTerm(
            term=term,
            best_translation=best_result.translation if best_result else None,
            best_confidence=best_result.confidence if best_result else 0.0,
            best_source=best_result.source if best_result else None,
            all_results=all_results
        )

    async def search_batch(
        self,
        terms: List[str],
        source_lang: str = "en",
        target_lang: str = "pl",
        sources: Optional[List[str]] = None
    ) -> List[EnrichedTerm]:
        """
        Search for multiple terms across all enabled databases.

        Args:
            terms: List of terms to search for
            source_lang: Source language code
            target_lang: Target language code
            sources: Optional list of sources to search

        Returns:
            List of EnrichedTerm results
        """
        import asyncio

        tasks = [
            self.search_term(term, source_lang, target_lang, sources)
            for term in terms
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched_results = []
        for term, result in zip(terms, results):
            if isinstance(result, Exception):
                logger.error(f"Batch search failed for '{term}': {result}")
                enriched_results.append(EnrichedTerm(
                    term=term,
                    best_translation=None,
                    best_confidence=0.0,
                    best_source=None,
                    all_results=[]
                ))
            else:
                enriched_results.append(result)

        return enriched_results

    def _select_best_result(
        self,
        results: List[TerminologyResult]
    ) -> Optional[TerminologyResult]:
        """
        Select the best result from multiple sources.

        Priority order (when translations available):
        1. IATE (most reliable EU terminology)
        2. CURIA (CJEU case law)
        3. HUDOC (ECHR case law)

        Args:
            results: List of results from different sources

        Returns:
            Best result or None
        """
        # Filter results with translations
        valid_results = [r for r in results if r.translation]

        if not valid_results:
            # No translations found, return result with highest confidence
            # (might have case references even without translation)
            if results:
                return max(results, key=lambda r: r.confidence)
            return None

        # Priority weights for sources
        source_weights = {
            "iate": 1.2,   # IATE is most authoritative
            "curia": 1.0,
            "hudoc": 0.9
        }

        # Calculate weighted scores
        def weighted_score(result: TerminologyResult) -> float:
            weight = source_weights.get(result.source, 1.0)
            return result.confidence * weight

        # Return result with highest weighted score
        return max(valid_results, key=weighted_score)

    def get_summary(self, enriched_term: EnrichedTerm) -> Dict[str, Any]:
        """
        Get a summary of search results for a term.

        Args:
            enriched_term: EnrichedTerm to summarize

        Returns:
            Dictionary with summary information
        """
        return {
            "term": enriched_term.term,
            "translation": enriched_term.best_translation,
            "confidence": enriched_term.best_confidence,
            "source": enriched_term.best_source,
            "sources_searched": len(enriched_term.all_results),
            "sources_with_results": sum(
                1 for r in enriched_term.all_results if r.translation
            ),
            "all_translations": [
                {
                    "source": r.source,
                    "translation": r.translation,
                    "confidence": r.confidence,
                    "references_count": len(r.references),
                    "domain": r.domain
                }
                for r in enriched_term.all_results
                if r.translation
            ]
        }

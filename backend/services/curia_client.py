"""CURIA Client - przeszukiwanie bazy orzeczeń TSUE."""

import logging
from typing import List, Dict, Any, Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)


class CURIAClient:
    """Klient do przeszukiwania bazy CURIA (Court of Justice of the European Union)."""

    def __init__(self):
        """Inicjalizacja CURIA Client."""
        self.base_url = settings.curia_base_url
        self.timeout = settings.curia_timeout_seconds
        self.max_retries = settings.curia_max_retries
        self.enabled = settings.curia_enabled
        logger.info(f"CURIA Client initialized (enabled: {self.enabled})")

    async def search_term(
        self, term: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Przeszukuje CURIA w poszukiwaniu terminu.

        Args:
            term: Termin do wyszukania
            max_results: Maksymalna liczba wyników

        Returns:
            Lista słowników z wynikami
        """
        if not self.enabled:
            logger.info("CURIA is disabled in configuration")
            return []

        try:
            logger.info(f"Searching CURIA for term: {term}")

            # Uproszczone wyszukiwanie - w pełnej wersji używałby API CURIA
            # lub web scraping
            results = await self._search_simple(term, max_results)

            logger.info(f"Found {len(results)} results in CURIA for '{term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching CURIA: {e}")
            return []

    def _normalize_term(self, term: str) -> str:
        """Normalize term for matching."""
        return term.lower().strip()

    def _extract_keywords(self, term: str) -> List[str]:
        """
        Extract keywords from a term by removing common stopwords.

        Args:
            term: Input term

        Returns:
            List of keywords
        """
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'that',
            'this', 'these', 'those', 'not', 'it', 'its'
        }

        words = term.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords

    def _calculate_match_score(self, query_term: str, known_term: str) -> float:
        """
        Calculate match score between query and known term.

        Scoring:
        - 1.0: Exact match
        - 0.9: All query keywords found in known term
        - 0.7-0.8: Partial keyword match (50%+ keywords)
        - 0.5-0.6: Some keywords match (25-50%)
        - 0.0: No match

        Args:
            query_term: Search query
            known_term: Known term from database

        Returns:
            Match score (0.0 to 1.0)
        """
        query_norm = self._normalize_term(query_term)
        known_norm = self._normalize_term(known_term)

        # Exact match
        if query_norm == known_norm:
            return 1.0

        # Check if one is substring of another
        if query_norm in known_norm:
            coverage = len(query_norm) / len(known_norm)
            return 0.85 + (coverage * 0.15)

        if known_norm in query_norm:
            coverage = len(known_norm) / len(query_norm)
            return 0.80 + (coverage * 0.15)

        # Keyword-based matching
        query_keywords = set(self._extract_keywords(query_term))
        known_keywords = set(self._extract_keywords(known_term))

        if not query_keywords or not known_keywords:
            return 0.0

        common_keywords = query_keywords.intersection(known_keywords)
        if not common_keywords:
            return 0.0

        query_coverage = len(common_keywords) / len(query_keywords)
        known_coverage = len(common_keywords) / len(known_keywords)
        avg_coverage = (query_coverage + known_coverage) / 2

        if avg_coverage >= 0.9:
            return 0.85
        elif avg_coverage >= 0.7:
            return 0.75
        elif avg_coverage >= 0.5:
            return 0.65
        elif avg_coverage >= 0.3:
            return 0.55
        else:
            return 0.0

    async def _search_simple(
        self, term: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Improved search with keyword extraction and fallback strategies.

        Strategies:
        1. Try exact match
        2. Try phrase match (all keywords present)
        3. Try partial match (some keywords present)
        4. Try individual keyword search

        Args:
            term: Termin
            max_results: Maks. wyników

        Returns:
            Lista wyników
        """
        # Przykładowe known terms z CURIA (terminologia UE)
        known_curia_terms = {
            "legal certainty": {
                "en": "legal certainty",
                "pl": "pewność prawa",
                "confidence": 0.95,
            },
            "proportionality": {
                "en": "proportionality",
                "pl": "proporcjonalność",
                "confidence": 0.95,
            },
            "legitimate expectation": {
                "en": "legitimate expectation",
                "pl": "uzasadnione oczekiwanie",
                "confidence": 0.9,
            },
            "direct effect": {
                "en": "direct effect",
                "pl": "bezpośrednie zastosowanie",
                "confidence": 0.95,
            },
            "preliminary ruling": {
                "en": "preliminary ruling",
                "pl": "orzeczenie prejudycjalne",
                "confidence": 1.0,
            },
            "free movement": {
                "en": "free movement",
                "pl": "swobodny przepływ",
                "confidence": 0.95,
            },
            "state aid": {
                "en": "State aid",
                "pl": "pomoc państwa",
                "confidence": 1.0,
            },
            "competition law": {
                "en": "competition law",
                "pl": "prawo konkurencji",
                "confidence": 0.95,
            },
            "directive": {
                "en": "Directive",
                "pl": "Dyrektywa",
                "confidence": 0.95,
            },
            "regulation": {
                "en": "Regulation",
                "pl": "Rozporządzenie",
                "confidence": 0.95,
            },
            "member state": {
                "en": "Member State",
                "pl": "Państwo Członkowskie",
                "confidence": 0.95,
            },
            "infringement": {
                "en": "infringement",
                "pl": "naruszenie",
                "confidence": 0.95,
            },
            "judicial review": {
                "en": "judicial review",
                "pl": "kontrola sądowa",
                "confidence": 0.90,
            },
            "annulment": {
                "en": "annulment",
                "pl": "stwierdzenie nieważności",
                "confidence": 0.90,
            },
        }

        # Calculate match scores for all known terms
        matches = []
        query_word_count = len(self._extract_keywords(term))

        for known_term, data in known_curia_terms.items():
            score = self._calculate_match_score(term, known_term)
            known_word_count = len(self._extract_keywords(known_term))

            # CRITICAL FIX: Penalize single-word matches for multi-word queries
            # If query has 3+ words but matched term has only 1 word, heavily penalize
            if query_word_count >= 3 and known_word_count == 1:
                score *= 0.3  # Reduce score by 70%

            # If query has 2+ words but matched term has only 1 word, moderately penalize
            elif query_word_count >= 2 and known_word_count == 1:
                score *= 0.5  # Reduce score by 50%

            if score > 0.5:  # Only include if score > 50%
                matches.append({
                    "known_term": known_term,
                    "data": data,
                    "score": score
                })

        # Sort by score (descending)
        matches.sort(key=lambda x: x["score"], reverse=True)

        # Build results
        results = []
        for match in matches[:max_results]:
            data = match["data"]
            adjusted_confidence = data["confidence"] * match["score"]

            result = {
                "source": "curia",
                "term_en": data["en"],
                "term_pl": data["pl"],
                "confidence": round(adjusted_confidence, 2),
                "url": f"{self.base_url}/juris/recherche.jsf?text={match['known_term'].replace(' ', '+')}",
                "match_score": round(match["score"], 2),
            }
            results.append(result)

        return results

    async def find_term_translation(
        self, term_en: str
    ) -> Optional[Dict[str, Any]]:
        """
        Znajduje polskie tłumaczenie terminu angielskiego.

        Args:
            term_en: Termin angielski

        Returns:
            Słownik z tłumaczeniem lub None
        """
        results = await self.search_term(term_en, max_results=1)

        if results:
            return results[0]

        return None

    async def get_multilingual_term(
        self, term: str, languages: List[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Pobiera tłumaczenia terminu w wielu językach UE.

        Args:
            term: Termin do wyszukania
            languages: Lista kodów języków (np. ['en', 'pl', 'de'])

        Returns:
            Słownik z tłumaczeniami lub None
        """
        if not self.enabled:
            return None

        languages = languages or ["en", "pl"]

        try:
            # Mock implementation
            # W pełnej wersji pobierałby z IATE (Inter-Active Terminology for Europe)
            result = await self.find_term_translation(term)

            if result:
                return {
                    "en": result["term_en"],
                    "pl": result["term_pl"],
                }

            return None

        except Exception as e:
            logger.error(f"Error getting multilingual term: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki klienta.

        Returns:
            Słownik ze statystykami
        """
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

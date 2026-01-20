"""HUDOC Client - przeszukiwanie bazy orzeczeń ETPCz."""

import logging
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from config import settings

logger = logging.getLogger(__name__)


class HUDOCClient:
    """Klient do przeszukiwania bazy HUDOC (European Court of Human Rights)."""

    def __init__(self):
        """Inicjalizacja HUDOC Client."""
        self.base_url = settings.hudoc_base_url
        self.timeout = settings.hudoc_timeout_seconds
        self.max_retries = settings.hudoc_max_retries
        self.enabled = settings.hudoc_enabled
        logger.info(f"HUDOC Client initialized (enabled: {self.enabled})")

    async def search_term(
        self, term: str, language: str = "ENG", max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Przeszukuje HUDOC w poszukiwaniu terminu.

        Args:
            term: Termin do wyszukania
            language: Język (ENG/POL)
            max_results: Maksymalna liczba wyników

        Returns:
            Lista słowników z wynikami
        """
        if not self.enabled:
            logger.info("HUDOC is disabled in configuration")
            return []

        try:
            logger.info(f"Searching HUDOC for term: {term}")

            # Uproszczone wyszukiwanie - w pełnej wersji używałby API HUDOC
            # lub web scraping
            results = await self._search_simple(term, language, max_results)

            logger.info(f"Found {len(results)} results in HUDOC for '{term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching HUDOC: {e}")
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
            # Calculate how much of known_term is covered
            coverage = len(query_norm) / len(known_norm)
            return 0.85 + (coverage * 0.15)  # 0.85 to 1.0

        if known_norm in query_norm:
            coverage = len(known_norm) / len(query_norm)
            return 0.80 + (coverage * 0.15)  # 0.80 to 0.95

        # Keyword-based matching
        query_keywords = set(self._extract_keywords(query_term))
        known_keywords = set(self._extract_keywords(known_term))

        if not query_keywords or not known_keywords:
            return 0.0

        # Calculate keyword overlap
        common_keywords = query_keywords.intersection(known_keywords)
        if not common_keywords:
            return 0.0

        # Score based on how many keywords match
        query_coverage = len(common_keywords) / len(query_keywords)
        known_coverage = len(common_keywords) / len(known_keywords)

        # Use average of both coverages
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
        self, term: str, language: str, max_results: int
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
            language: Język
            max_results: Maks. wyników

        Returns:
            Lista wyników
        """
        # Przykładowe known terms z HUDOC
        known_hudoc_terms = {
            "margin of appreciation": {
                "en": "margin of appreciation",
                "pl": "margines oceny",
                "cases": ["Handyside v. United Kingdom", "Sunday Times v. United Kingdom"],
                "confidence": 1.0,
            },
            "just satisfaction": {
                "en": "just satisfaction",
                "pl": "słuszne zadośćuczynienie",
                "cases": ["Tyrer v. United Kingdom", "Soering v. United Kingdom"],
                "confidence": 1.0,
            },
            "applicant": {
                "en": "applicant",
                "pl": "skarżący",
                "cases": ["Various cases"],
                "confidence": 1.0,
            },
            "respondent government": {
                "en": "respondent Government",
                "pl": "pozwany Rząd",
                "cases": ["Various cases"],
                "confidence": 1.0,
            },
            "government": {
                "en": "Government",
                "pl": "Rząd",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "convention": {
                "en": "Convention",
                "pl": "Konwencja",
                "cases": ["Various cases"],
                "confidence": 1.0,
            },
            "admissibility": {
                "en": "admissibility",
                "pl": "dopuszczalność",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "merits": {
                "en": "merits",
                "pl": "meritum",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "violation": {
                "en": "violation",
                "pl": "naruszenie",
                "cases": ["Various cases"],
                "confidence": 1.0,
            },
            "article": {
                "en": "Article",
                "pl": "Artykuł",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "protocol": {
                "en": "Protocol",
                "pl": "Protokół",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "court": {
                "en": "Court",
                "pl": "Trybunał",
                "cases": ["Various cases"],
                "confidence": 0.90,
            },
            "judgment": {
                "en": "judgment",
                "pl": "wyrok",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
            "decision": {
                "en": "decision",
                "pl": "decyzja",
                "cases": ["Various cases"],
                "confidence": 0.95,
            },
        }

        # Calculate match scores for all known terms
        matches = []
        for known_term, data in known_hudoc_terms.items():
            score = self._calculate_match_score(term, known_term)

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
            # Adjust confidence based on match score
            adjusted_confidence = data["confidence"] * match["score"]

            result = {
                "source": "hudoc",
                "term_en": data["en"],
                "term_pl": data["pl"],
                "cases": data["cases"][:max_results],
                "confidence": round(adjusted_confidence, 2),
                "url": f"{self.base_url}/eng?i={match['known_term'].replace(' ', '+')}",
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

    async def get_case_details(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera szczegóły sprawy z HUDOC.

        Args:
            case_id: ID sprawy

        Returns:
            Słownik ze szczegółami lub None
        """
        if not self.enabled:
            return None

        try:
            # Mock implementation
            return {
                "case_id": case_id,
                "title": "Example Case v. Country",
                "date": "2024-01-01",
                "url": f"{self.base_url}/eng?i={case_id}",
            }
        except Exception as e:
            logger.error(f"Error getting case details: {e}")
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

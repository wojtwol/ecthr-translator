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

    async def _search_simple(
        self, term: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Proste wyszukiwanie (mock dla Sprint 3).

        W pełnej implementacji użyłby CURIA API lub web scraping.

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
        }

        # Wyszukaj w known terms
        term_lower = term.lower().strip()
        results = []

        for known_term, data in known_curia_terms.items():
            if term_lower in known_term or known_term in term_lower:
                result = {
                    "source": "curia",
                    "term_en": data["en"],
                    "term_pl": data["pl"],
                    "confidence": data["confidence"],
                    "url": f"{self.base_url}/juris/recherche.jsf?text={known_term.replace(' ', '+')}",
                }
                results.append(result)

                if len(results) >= max_results:
                    break

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

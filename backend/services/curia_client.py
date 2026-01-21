"""CURIA Client - przeszukiwanie bazy orzeczeń TSUE."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import httpx
import re
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

    def _strip_articles(self, term: str) -> str:
        """
        Remove articles from the beginning of the term.

        Terminology databases store terms WITHOUT articles:
        - "intervener" not "the intervener"
        - "applicant" not "an applicant"
        - "court" not "a court"

        Args:
            term: Original term (may start with article)

        Returns:
            Term without leading article
        """
        articles = ['the ', 'a ', 'an ']
        term_lower = term.lower()

        for article in articles:
            if term_lower.startswith(article):
                # Remove article and preserve original casing of remaining text
                stripped = term[len(article):]
                logger.debug(f"Stripped article: '{term}' → '{stripped}'")
                return stripped

        return term

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
            # CRITICAL: Strip articles before searching (databases don't include them)
            search_term = self._strip_articles(term)
            logger.info(f"Searching CURIA for term: '{term}' (normalized: '{search_term}')")

            # Uproszczone wyszukiwanie - w pełnej wersji używałby API CURIA
            # lub web scraping
            results = await self._search_simple(search_term, max_results)

            logger.info(f"Found {len(results)} results in CURIA for '{search_term}'")
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

        # CRITICAL FIX: Prevent single-word queries from matching multi-word phrases
        # "court" (1 word) should NEVER match "access to court" (3 words)
        # They are completely different legal concepts!
        query_word_count = len(query_term.split())
        known_word_count = len(known_term.split())

        # Strict word count matching for short queries (1-2 words)
        # Single-word query can ONLY match 1-2 word terms (not 3+)
        # Two-word query can ONLY match 1-3 word terms (not 4+)
        if query_word_count <= 2:
            max_allowed_diff = 1  # Allow difference of max 1 word
            if abs(query_word_count - known_word_count) > max_allowed_diff:
                return 0.0  # Reject - word count too different for short query

        common_keywords = query_keywords.intersection(known_keywords)
        if not common_keywords:
            return 0.0

        query_coverage = len(common_keywords) / len(query_keywords)
        known_coverage = len(common_keywords) / len(known_keywords)

        # CRITICAL FIX: Stricter coverage requirements for short queries
        # Short queries (1-2 words) need HIGHER coverage to avoid false positives
        # "District Court" (50%) should NOT match "access to court" (50%)
        # They are different legal concepts despite sharing "court"
        if query_word_count <= 2:
            # Require 70% coverage for both sides (was 50%)
            if query_coverage < 0.7 or known_coverage < 0.7:
                return 0.0  # Reject - insufficient match for short query
        else:
            # For longer queries (3+ words), keep 50% threshold
            if query_coverage < 0.5 or known_coverage < 0.5:
                return 0.0  # Reject - insufficient match on at least one side

        avg_coverage = (query_coverage + known_coverage) / 2

        if avg_coverage >= 0.9:
            return 0.85
        elif avg_coverage >= 0.7:
            return 0.75
        elif avg_coverage >= 0.5:
            return 0.65
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
        # Count ACTUAL words, not keywords (keywords filter removes stopwords)
        # "access to court" = 3 words (not 2 after removing "to")
        query_word_count = len(term.split())

        for known_term, data in known_curia_terms.items():
            # Count ACTUAL words in known term
            known_word_count = len(known_term.split())

            # CRITICAL: STRICT word count filtering - legal principle
            # Don't extract single words from multi-word concepts and vice versa
            # But remember: EN and PL can have different word counts!
            # We only compare EN source terms (query vs known_term)
            word_count_diff = abs(query_word_count - known_word_count)

            # REJECT matches with large word count difference
            # "right" (1 word) should NEVER match "fundamental rights" (2 words)
            # "access to court" (3 words) should NEVER match "court" (1 word)
            if query_word_count == 1 and known_word_count > 2:
                continue  # Single word query can't match 3+ word terms
            if query_word_count >= 3 and known_word_count == 1:
                continue  # Multi-word query (3+) can't match single word
            if word_count_diff > 2:
                continue  # Max difference is 2 words for any match

            score = self._calculate_match_score(term, known_term)

            # Additional penalty for remaining word count mismatches
            if query_word_count >= 2 and known_word_count == 1:
                score *= 0.5  # Reduce score by 50% for 2-word query vs 1-word term

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

    @staticmethod
    def detect_cjeu_citations(text: str) -> List[Dict[str, Any]]:
        """
        Wykrywa cytaty z wyroków TSUE w tekście.

        Szuka:
        - Sygnatur C-xxx/xx (np. C-487/19)
        - Identyfikatorów ECLI (np. EU:C:2021:798)

        Args:
            text: Tekst do przeszukania

        Returns:
            Lista wykrytych cytatów z metadanymi
        """
        citations = []

        # Regex dla sygnatur TSUE: C-xxx/xx
        case_number_pattern = r'\b(C-\d+/\d+)\b'

        # Regex dla ECLI: EU:C:YYYY:NNNN
        ecli_pattern = r'\b(EU:C:\d{4}:\d+)\b'

        # Znajdź wszystkie sygnatury
        for match in re.finditer(case_number_pattern, text):
            case_number = match.group(1)
            start_pos = match.start()

            # Spróbuj znaleźć powiązany ECLI w pobliżu (w ciągu 200 znaków)
            nearby_text = text[max(0, start_pos - 100):start_pos + 100]
            ecli_match = re.search(ecli_pattern, nearby_text)
            ecli = ecli_match.group(1) if ecli_match else None

            citations.append({
                "case_number": case_number,
                "ecli": ecli,
                "position": start_pos,
            })

        logger.info(f"Detected {len(citations)} CJEU citations in text")
        return citations

    async def get_judgment_by_case_number(
        self,
        case_number: str,
        source_lang: str = "EN",
        target_lang: str = "PL"
    ) -> Optional[Dict[str, Any]]:
        """
        Pobiera wyrok TSUE przez web scraping.

        Args:
            case_number: Sygnatura sprawy (np. "C-487/19")
            source_lang: Język źródłowy (EN)
            target_lang: Język docelowy (PL)

        Returns:
            Słownik z treścią wyroku w obu językach lub None
        """
        if not self.enabled:
            logger.info("CURIA is disabled")
            return None

        try:
            logger.info(f"Fetching CJEU judgment {case_number} ({source_lang} -> {target_lang})")

            # CURIA URLs dla różnych języków
            # Format: https://curia.europa.eu/juris/liste.jsf?num=C-487/19&language=pl
            url_base = "https://curia.europa.eu/juris/liste.jsf"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Pobierz listę dokumentów dla tej sprawy
                params = {
                    "num": case_number,
                    "language": target_lang.lower()
                }

                response = await client.get(url_base, params=params)
                response.raise_for_status()

                # Parsowanie prostsze - zwróć URL do tłumaczenia
                # W pełnej implementacji użyłbyś BeautifulSoup do parsowania HTML
                # i wyodrębnienia paragrafów

                result = {
                    "case_number": case_number,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "url": response.url,
                    "paragraphs": [],  # W pełnej wersji: lista {para_num, text_en, text_pl}
                    "available": response.status_code == 200,
                }

                logger.info(f"Successfully fetched judgment {case_number}")
                return result

        except Exception as e:
            logger.error(f"Error fetching CJEU judgment {case_number}: {e}")
            return None

    async def extract_judgment_paragraphs(
        self,
        case_number: str,
        paragraph_numbers: List[int]
    ) -> Dict[int, Tuple[str, str]]:
        """
        Ekstrahuje konkretne paragrafy z wyroku TSUE (EN i PL).

        Args:
            case_number: Sygnatura sprawy
            paragraph_numbers: Lista numerów paragrafów do wyekstrakcji

        Returns:
            Słownik {para_num: (text_en, text_pl)}
        """
        # W pełnej implementacji:
        # 1. Pobierz wyrok w EN
        # 2. Pobierz wyrok w PL
        # 3. Wyekstrahuj konkretne paragrafy
        # 4. Zwróć je jako pary EN-PL

        logger.info(f"Extracting paragraphs {paragraph_numbers} from {case_number}")

        # Placeholder - zwróć puste
        return {}

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

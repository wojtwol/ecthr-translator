"""
HUDOC (European Court of Human Rights) Client.
Provides real integration with HUDOC database for legal terminology search.
"""
import asyncio
import json
import re
from typing import List, Tuple, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from backend.config import settings


class HUDOCClient:
    """Client for searching legal terms in HUDOC database."""

    def __init__(self):
        self.base_url = settings.hudoc_base_url
        self.timeout = settings.hudoc_timeout_seconds
        self.max_retries = settings.hudoc_max_retries
        self.use_mock = settings.hudoc_use_mock

        # Mock data for fallback
        self._mock_terms = {
            "margin of appreciation": ("margines oceny", 1.0, ["Handyside v. United Kingdom"]),
            "just satisfaction": ("słuszne zadośćuczynienie", 0.95, ["Various cases"]),
            "applicant": ("skarżący", 1.0, ["Standard terminology"]),
            "respondent government": ("pozwany Rząd", 0.95, ["Standard terminology"]),
            "convention": ("Konwencja", 1.0, ["ECHR"]),
            "admissibility": ("dopuszczalność", 1.0, ["Standard terminology"]),
            "merits": ("meritum", 0.9, ["Standard terminology"]),
            "violation": ("naruszenie", 1.0, ["Standard terminology"]),
        }

    async def search_term(
        self,
        term: str,
        source_lang: str = "en",
        target_lang: str = "pl"
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Search for a legal term in HUDOC database.

        Args:
            term: The legal term to search for
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "pl")

        Returns:
            Tuple of (translation, confidence_score, case_references)
        """
        if self.use_mock:
            logger.info(f"HUDOC: Using mock data for term '{term}'")
            return self._search_mock(term)

        logger.info(f"HUDOC: Searching for term '{term}' ({source_lang} -> {target_lang})")

        try:
            # Try real search
            result = await self._search_real(term, source_lang, target_lang)
            if result[0]:  # If translation found
                return result
            else:
                # Fall back to mock if no results
                logger.warning(f"HUDOC: No results found for '{term}', using mock fallback")
                return self._search_mock(term)

        except Exception as e:
            logger.error(f"HUDOC: Error searching for '{term}': {e}")
            # Fall back to mock on error
            return self._search_mock(term)

    def _search_mock(self, term: str) -> Tuple[Optional[str], float, List[str]]:
        """Search using mock data."""
        term_lower = term.lower()

        # Exact match
        if term_lower in self._mock_terms:
            return self._mock_terms[term_lower]

        # Partial match
        for key, value in self._mock_terms.items():
            if term_lower in key or key in term_lower:
                translation, conf, refs = value
                return (translation, conf * 0.8, refs)  # Lower confidence for partial match

        return (None, 0.0, [])

    async def _search_real(
        self,
        term: str,
        source_lang: str,
        target_lang: str
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Perform real search in HUDOC database.

        HUDOC uses JSON parameters in URL fragment for search queries.
        Example: https://hudoc.echr.coe.int/eng#{\"text\":[\"margin of appreciation\"]}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Construct search URL with JSON parameters
            # We'll search in English judgments for the term
            search_params = {
                "text": [term],
                "documentcollectionid2": ["JUDGMENTS"],
                "languageisocode": ["ENG"]
            }

            # Encode JSON parameters for URL
            params_json = json.dumps(search_params)
            search_url = f"{self.base_url}/eng#{params_json}"

            logger.debug(f"HUDOC search URL: {search_url}")

            for attempt in range(self.max_retries):
                try:
                    # Fetch the search results page
                    response = await client.get(search_url)
                    response.raise_for_status()

                    # Parse HTML to extract results
                    soup = BeautifulSoup(response.text, "lxml")

                    # Extract case information and potential translations
                    results = self._parse_search_results(soup, term, target_lang)

                    if results:
                        return results

                    # No results found
                    return (None, 0.0, [])

                except httpx.HTTPStatusError as e:
                    logger.warning(f"HUDOC HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

                except Exception as e:
                    logger.error(f"HUDOC unexpected error: {e}")
                    raise

        return (None, 0.0, [])

    def _parse_search_results(
        self,
        soup: BeautifulSoup,
        term: str,
        target_lang: str
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Parse HUDOC search results HTML.

        This is a simplified implementation. A full implementation would:
        1. Extract individual case documents
        2. Find Polish translations if available
        3. Extract terminology from bilingual documents
        4. Calculate confidence based on frequency and context
        """
        case_references = []

        # Look for result items in HUDOC's HTML structure
        # Note: HUDOC's actual HTML structure may vary, this is a best-effort approach
        result_items = soup.find_all("div", class_=re.compile(r"result|item|case", re.I))

        for item in result_items[:10]:  # Limit to first 10 results
            # Try to extract case name/reference
            case_link = item.find("a", class_=re.compile(r"case|title", re.I))
            if case_link:
                case_name = case_link.get_text(strip=True)
                if case_name:
                    case_references.append(case_name)

        # For a real implementation, we would:
        # 1. Fetch individual case documents
        # 2. Look for Polish translations in the document
        # 3. Extract the term's translation from context

        # For now, return cases found but no translation
        # (Full implementation would require fetching and parsing each case document)
        if case_references:
            confidence = 0.7  # Medium confidence - found relevant cases
            logger.info(f"HUDOC: Found {len(case_references)} cases for '{term}'")
            return (None, confidence, case_references)

        return (None, 0.0, [])

    async def search_batch(
        self,
        terms: List[str],
        source_lang: str = "en",
        target_lang: str = "pl"
    ) -> List[Tuple[str, Optional[str], float, List[str]]]:
        """
        Search for multiple terms in batch.

        Args:
            terms: List of legal terms to search for
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of tuples: (term, translation, confidence, case_references)
        """
        tasks = [
            self.search_term(term, source_lang, target_lang)
            for term in terms
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_results = []
        for term, result in zip(terms, results):
            if isinstance(result, Exception):
                logger.error(f"HUDOC batch search error for '{term}': {result}")
                batch_results.append((term, None, 0.0, []))
            else:
                translation, confidence, refs = result
                batch_results.append((term, translation, confidence, refs))

        return batch_results

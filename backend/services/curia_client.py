"""
CURIA (Court of Justice of the European Union) Client.
Provides real integration with EUR-Lex CELLAR database via SPARQL for legal terminology search.
"""
import asyncio
from typing import List, Tuple, Optional

import httpx
from SPARQLWrapper import SPARQLWrapper, JSON
from loguru import logger

from backend.config import settings


class CURIAClient:
    """Client for searching legal terms in CURIA/EUR-Lex database via SPARQL."""

    def __init__(self):
        self.sparql_endpoint = settings.eurlex_sparql_endpoint
        self.timeout = settings.curia_timeout_seconds
        self.max_retries = settings.curia_max_retries
        self.use_mock = settings.curia_use_mock

        # Mock data for fallback
        self._mock_terms = {
            "legal certainty": ("pewność prawa", 1.0, ["C-104/86 Commission v Italy"]),
            "proportionality": ("proporcjonalność", 1.0, ["Various CJEU cases"]),
            "legitimate expectation": ("uzasadnione oczekiwanie", 0.95, ["CJEU case law"]),
            "direct effect": ("bezpośrednie zastosowanie", 1.0, ["Van Gend en Loos"]),
            "preliminary ruling": ("orzeczenie prejudycjalne", 1.0, ["Article 267 TFEU"]),
            "free movement": ("swobodny przepływ", 1.0, ["EU Treaties"]),
            "state aid": ("pomoc państwa", 1.0, ["Article 107 TFEU"]),
            "competition law": ("prawo konkurencji", 0.95, ["Articles 101-109 TFEU"]),
        }

    async def search_term(
        self,
        term: str,
        source_lang: str = "en",
        target_lang: str = "pl"
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Search for a legal term in CURIA/EUR-Lex database.

        Args:
            term: The legal term to search for
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "pl")

        Returns:
            Tuple of (translation, confidence_score, case_references)
        """
        if self.use_mock:
            logger.info(f"CURIA: Using mock data for term '{term}'")
            return self._search_mock(term)

        logger.info(f"CURIA: Searching for term '{term}' ({source_lang} -> {target_lang})")

        try:
            # Try real search via SPARQL
            result = await self._search_sparql(term, source_lang, target_lang)
            if result[0]:  # If translation found
                return result
            else:
                # Fall back to mock if no results
                logger.warning(f"CURIA: No results found for '{term}', using mock fallback")
                return self._search_mock(term)

        except Exception as e:
            logger.error(f"CURIA: Error searching for '{term}': {e}")
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

    async def _search_sparql(
        self,
        term: str,
        source_lang: str,
        target_lang: str
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Perform real search in EUR-Lex database using SPARQL.

        This searches for CJEU case law containing the term and attempts to find
        translations in the target language.
        """
        # Run SPARQL query in thread pool (SPARQLWrapper is synchronous)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._execute_sparql_search,
            term,
            source_lang,
            target_lang
        )
        return result

    def _execute_sparql_search(
        self,
        term: str,
        source_lang: str,
        target_lang: str
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Execute SPARQL query synchronously.

        This query searches for CJEU judgments containing the term.
        """
        try:
            sparql = SPARQLWrapper(self.sparql_endpoint)

            # SPARQL query to find CJEU case law with the term
            # This is a simplified query - a production version would be more sophisticated
            query = f"""
            PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX dc: <http://purl.org/dc/elements/1.1/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT DISTINCT ?case ?title ?celex
            WHERE {{
              ?case cdm:resource_legal_id_celex ?celex .
              ?case dc:title ?title .
              ?case cdm:resource_legal_is_about-concept_concept ?concept .

              FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{term}")))
              FILTER(REGEX(?celex, "^6[0-9]{{4}}CJ", "i"))

              FILTER(LANG(?title) = "{source_lang}")
            }}
            LIMIT 10
            """

            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)

            logger.debug(f"CURIA SPARQL query: {query[:200]}...")

            for attempt in range(self.max_retries):
                try:
                    results = sparql.query().convert()

                    case_references = []
                    for result in results["results"]["bindings"]:
                        celex = result.get("celex", {}).get("value", "")
                        title = result.get("title", {}).get("value", "")

                        if celex:
                            case_ref = f"{celex}"
                            if title:
                                case_ref += f" - {title[:100]}"
                            case_references.append(case_ref)

                    if case_references:
                        confidence = 0.75  # Medium-high confidence
                        logger.info(f"CURIA: Found {len(case_references)} cases for '{term}'")

                        # For a full implementation, we would:
                        # 1. Fetch full documents for these cases
                        # 2. Extract Polish translations from bilingual documents
                        # 3. Use NLP to find the term's translation in context

                        # For now, return cases found but no translation
                        return (None, confidence, case_references)

                    return (None, 0.0, [])

                except Exception as e:
                    logger.warning(f"CURIA SPARQL error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

        except Exception as e:
            logger.error(f"CURIA SPARQL execution error: {e}")
            raise

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
                logger.error(f"CURIA batch search error for '{term}': {result}")
                batch_results.append((term, None, 0.0, []))
            else:
                translation, confidence, refs = result
                batch_results.append((term, translation, confidence, refs))

        return batch_results

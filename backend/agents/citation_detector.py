"""Citation Detector - wykrywa cytowania wyroków w tekście."""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class CitationDetector:
    """
    Wykrywa cytowania wyroków ETPCz i TSUE w tekście źródłowym.

    Faza 1 (MVP): Tylko detekcja cytowań, bez pobierania terminologii.
    Faza 2 (przyszłość): Pobieranie terminów z cytowanych wyroków.
    """

    # Wzorce dla wyroków ETPCz (HUDOC)
    HUDOC_PATTERNS = [
        # "Smith v. United Kingdom"
        r'\b([A-Z][a-z]+(?:\s+and\s+Others)?)\s+v\.\s+([A-Z][a-z]+(?:\s+Kingdom)?)\b',

        # "Case of Smith v. United Kingdom"
        r'Case\s+of\s+([A-Z][a-z]+(?:\s+and\s+Others)?)\s+v\.\s+([A-Z][a-z]+(?:\s+Kingdom)?)\b',

        # "[GC] Müller v. Austria" (Grand Chamber)
        r'\[GC\]\s+([A-Z][a-zü]+)\s+v\.\s+([A-Z][a-z]+)\b',

        # "Smith and Others v. United Kingdom"
        r'\b([A-Z][a-z]+\s+and\s+Others)\s+v\.\s+([A-Z][a-z]+(?:\s+Kingdom)?)\b',

        # With application number: "Smith v. UK, no. 12345/67"
        r'\b([A-Z][a-z]+)\s+v\.\s+([A-Z]{2,}),?\s+(?:no\.|application\s+no\.)\s+(\d+/\d+)\b',
    ]

    # Wzorce dla wyroków TSUE (CURIA)
    CURIA_PATTERNS = [
        # "Case C-123/45"
        r'Case\s+(C-\d+/\d+)',

        # "Joined Cases C-123/45 and C-456/78"
        r'Joined\s+Cases\s+(C-\d+/\d+(?:\s+and\s+C-\d+/\d+)+)',

        # In text: "in Case C-123/45"
        r'in\s+[Cc]ase\s+(C-\d+/\d+)',
    ]

    def __init__(self):
        """Inicjalizacja Citation Detector."""
        logger.info("CitationDetector initialized (detection-only mode)")

        # Compile patterns for performance
        self.hudoc_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.HUDOC_PATTERNS]
        self.curia_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.CURIA_PATTERNS]

    def detect_citations(self, source_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Wykrywa cytowania wyroków w tekście źródłowym.

        Args:
            source_text: Tekst źródłowy (EN) do przeskanowania

        Returns:
            Słownik z listami wykrytych cytowań:
            {
                "hudoc": [{"citation": "Smith v. UK", "position": 123, ...}, ...],
                "curia": [{"citation": "C-123/45", "position": 456, ...}, ...]
            }
        """
        try:
            logger.info("Starting citation detection...")

            hudoc_citations = self._detect_hudoc(source_text)
            curia_citations = self._detect_curia(source_text)

            total = len(hudoc_citations) + len(curia_citations)
            logger.info(f"Citation detection complete: {len(hudoc_citations)} HUDOC, {len(curia_citations)} CURIA (total: {total})")

            return {
                "hudoc": hudoc_citations,
                "curia": curia_citations,
                "total": total
            }

        except Exception as e:
            logger.error(f"Error during citation detection: {e}", exc_info=True)
            return {"hudoc": [], "curia": [], "total": 0}

    def _detect_hudoc(self, text: str) -> List[Dict[str, Any]]:
        """Wykrywa cytowania wyroków HUDOC."""
        citations = []
        seen = set()  # Avoid duplicates

        for pattern in self.hudoc_regex:
            for match in pattern.finditer(text):
                # Extract citation text
                citation_text = match.group(0).strip()

                # Avoid duplicates
                if citation_text.lower() in seen:
                    continue
                seen.add(citation_text.lower())

                citation = {
                    "citation": citation_text,
                    "source": "hudoc",
                    "position": match.start(),
                    "context": self._get_context(text, match.start(), match.end()),
                }

                # Try to extract applicant and respondent
                groups = match.groups()
                if len(groups) >= 2:
                    citation["applicant"] = groups[0].strip()
                    citation["respondent"] = groups[1].strip()

                citations.append(citation)
                logger.debug(f"Found HUDOC citation: {citation_text}")

        return citations

    def _detect_curia(self, text: str) -> List[Dict[str, Any]]:
        """Wykrywa cytowania wyroków CURIA."""
        citations = []
        seen = set()  # Avoid duplicates

        for pattern in self.curia_regex:
            for match in pattern.finditer(text):
                # Extract citation text
                citation_text = match.group(0).strip()

                # Avoid duplicates
                if citation_text.lower() in seen:
                    continue
                seen.add(citation_text.lower())

                citation = {
                    "citation": citation_text,
                    "source": "curia",
                    "position": match.start(),
                    "context": self._get_context(text, match.start(), match.end()),
                }

                # Try to extract case number
                groups = match.groups()
                if len(groups) >= 1:
                    citation["case_number"] = groups[0].strip()

                citations.append(citation)
                logger.debug(f"Found CURIA citation: {citation_text}")

        return citations

    def _get_context(self, text: str, start: int, end: int, context_chars: int = 100) -> str:
        """
        Zwraca kontekst wokół cytowania.

        Args:
            text: Pełny tekst
            start: Pozycja początku cytowania
            end: Pozycja końca cytowania
            context_chars: Ile znaków kontekstu przed i po

        Returns:
            Fragment tekstu z kontekstem
        """
        ctx_start = max(0, start - context_chars)
        ctx_end = min(len(text), end + context_chars)

        context = text[ctx_start:ctx_end].strip()

        # Add ellipsis if truncated
        if ctx_start > 0:
            context = "..." + context
        if ctx_end < len(text):
            context = context + "..."

        return context

    def get_summary(self, citations: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generuje czytelne podsumowanie wykrytych cytowań.

        Args:
            citations: Wynik z detect_citations()

        Returns:
            Tekst podsumowania
        """
        hudoc = citations.get("hudoc", [])
        curia = citations.get("curia", [])
        total = citations.get("total", 0)

        if total == 0:
            return "No case citations detected in the source text."

        lines = [f"\n📚 Citation Detection Summary ({total} citations found):"]

        if hudoc:
            lines.append(f"\n⚖️ HUDOC Citations ({len(hudoc)}):")
            for i, cite in enumerate(hudoc, 1):
                lines.append(f"  {i}. {cite['citation']}")
                if 'applicant' in cite and 'respondent' in cite:
                    lines.append(f"     Applicant: {cite['applicant']} | Respondent: {cite['respondent']}")

        if curia:
            lines.append(f"\n🏛️ CURIA Citations ({len(curia)}):")
            for i, cite in enumerate(curia, 1):
                lines.append(f"  {i}. {cite['citation']}")
                if 'case_number' in cite:
                    lines.append(f"     Case Number: {cite['case_number']}")

        return "\n".join(lines)

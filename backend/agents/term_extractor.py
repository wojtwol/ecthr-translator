"""Term Extractor - ekstrahuje terminy prawnicze z tekstu."""

import logging
import json
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_case_law_researcher = None


class TermExtractor:
    """Ekstrahuje terminy prawnicze z segmentów."""

    TERM_EXTRACTOR_PROMPT = """Jesteś ekspertem w terminologii prawniczej ETPCz.

CRITICAL: Extract and suggest translations ONLY for terms that are actually present in the segment.
DO NOT invent, add, or infer any terms or context that are not in the source text.

Przeanalizuj poniższy segment orzeczenia ETPCz i zidentyfikuj wszystkie terminy prawnicze,
które wymagają spójnego tłumaczenia:

Segment:
{segment_text}

Typ sekcji: {section_type}

Znane terminy z pamięci tłumaczeniowej:
{known_terms}

Zidentyfikuj NOWE terminy (nie obecne w pamięci tłumaczeniowej) i zaproponuj polskie ekwiwalenty.

Skup się na:
- Terminach specyficznych dla ETPCz (margin of appreciation, just satisfaction, etc.)
- Terminach proceduralnych (applicant, respondent Government, etc.)
- Nazwach artykułów Konwencji i Protokołów
- Łacińskich maksymach prawniczych
- PEŁNYCH nazwach sądów i instytucji

CRITICAL RULES:
1. Extract ONLY terms that appear in the segment above
2. Use the exact phrase from the segment as "context" - do not paraphrase or invent
3. DO NOT add terms that are not in the segment
4. DO NOT complete or infer missing information

CRITICAL RULES FOR COURT/INSTITUTION NAMES:
5. Extract FULL names of courts and institutions, NOT individual words
   ✓ CORRECT: "Warsaw Court of Appeal" → "Sąd Apelacyjny w Warszawie"
   ✗ WRONG: "Appeal" alone (missing context - which appeal?)
   ✓ CORRECT: "Supreme Court" → "Sąd Najwyższy"
   ✗ WRONG: "Court" alone (missing which court)
   ✓ CORRECT: "District Court of Warsaw" → "Sąd Rejonowy w Warszawie"
   ✗ WRONG: "District Court" without location

6. For proper names of institutions, extract the complete official name:
   ✓ "European Court of Human Rights"
   ✓ "Constitutional Tribunal"
   ✓ "National Council of the Judiciary"
   ✗ NOT: "Tribunal" alone
   ✗ NOT: "Council" alone

CRITICAL RULES FOR CONTEXT-DEPENDENT TERMS:
7. The SAME word can have DIFFERENT translations depending on context!
   Extract each occurrence separately with its specific context and translation:

   Example with "appeal":
   ✓ "Court of Appeal" → "Sąd Apelacyjny" (institution name)
   ✓ "filed an appeal" → "wniosła apelację" (judicial remedy to court)
   ✓ "submitted an appeal to the Ministry" → "złożył odwołanie" (administrative appeal to non-court body)

   Example with "application":
   ✓ "the application to the Court" → "skarga do Trybunału" (ECtHR complaint)
   ✓ "application for leave to appeal" → "wniosek o dopuszczenie apelacji" (procedural motion)

   Example with "court":
   ✓ "the Warsaw Regional Court" → "Sąd Okręgowy w Warszawie" (specific court)
   ✓ "appeared in court" → "stawił się w sądzie" (generic reference)

8. ALWAYS include rich context showing HOW the term is used:
   - Include surrounding words that clarify meaning
   - Show if it's part of a procedural phrase
   - Indicate if referring to institution vs. action
   - Preserve grammatical context (e.g., "filed an appeal", not just "appeal")

Odpowiedz w formacie JSON:
{{
    "terms": [
        {{
            "source_term": "margin of appreciation",
            "proposed_translation": "margines oceny",
            "context": "exact sentence from segment where term appears (include 5-10 words around the term for clarity)",
            "term_type": "ecthr_specific" | "procedural" | "convention" | "latin" | "court_name" | "institution",
            "confidence": 0.0-1.0
        }}
    ]
}}

Jeśli nie znalazłeś żadnych nowych terminów, zwróć pustą listę: {{"terms": []}}"""

    def __init__(self, enable_case_law_research: bool = True):
        """
        Inicjalizacja Term Extractor.

        Args:
            enable_case_law_research: Czy włączyć wzbogacanie terminów z baz orzeczeń
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.extracted_terms_cache = {}  # Cache dla już wyekstrahowanych terminów
        self.enable_case_law_research = enable_case_law_research
        self.case_law_researcher = None
        logger.info(f"Term Extractor initialized (case law research: {enable_case_law_research})")

    def _get_case_law_researcher(self):
        """
        Lazy initialization of Case Law Researcher.

        Returns:
            CaseLawResearcher instance
        """
        if not self.enable_case_law_research:
            return None

        if self.case_law_researcher is None:
            from agents.case_law_researcher import CaseLawResearcher
            self.case_law_researcher = CaseLawResearcher()

        return self.case_law_researcher

    async def extract(
        self,
        segments: List[Dict[str, Any]],
        known_terms: Optional[List[Dict[str, str]]] = None,
        document_id: Optional[str] = None,
        ws_manager = None,
        current_progress: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Ekstrahuje terminy prawnicze z segmentów.

        Args:
            segments: Lista segmentów z tekstem i section_type
            known_terms: Lista znanych terminów z TM

        Returns:
            Lista zekstrahowanych terminów
        """
        known_terms = known_terms or []
        all_terms = []

        # Przygotuj listę znanych terminów do przekazania
        known_terms_text = self._format_known_terms(known_terms)

        for i, segment in enumerate(segments):
            try:
                segment_text = segment.get("text", "")
                section_type = segment.get("section_type", "OTHER")

                # Pomiń bardzo krótkie segmenty
                if len(segment_text.strip()) < 30:
                    continue

                # Ekstrahuj terminy z segmentu
                terms = await self._extract_from_segment(
                    segment_text, section_type, known_terms_text
                )

                # Dodaj informację o segmencie
                for term in terms:
                    term["segment_index"] = i
                    term["source_segment"] = segment_text

                    # CRITICAL: Cache key includes context to allow same term with different meanings
                    # Example: "appeal" in "Court of Appeal" vs "filed an appeal" vs "appeal to Ministry"
                    # Each needs separate entry with different translation
                    context_snippet = term.get("context", "")[:100]  # First 100 chars for cache key
                    term_key = f"{term['source_term'].lower()}|{context_snippet.lower()}"

                    if term_key not in self.extracted_terms_cache:
                        self.extracted_terms_cache[term_key] = term
                        all_terms.append(term)

                logger.debug(f"Segment {i}: extracted {len(terms)} terms")

            except Exception as e:
                logger.error(f"Error extracting terms from segment {i}: {e}")

        logger.info(f"Extracted {len(all_terms)} unique terms from {len(segments)} segments")

        # Wzbogać terminy o wyniki z baz orzeczeń (HUDOC, CURIA, IATE)
        if self.enable_case_law_research and all_terms:
            try:
                researcher = self._get_case_law_researcher()
                if researcher:
                    if ws_manager and document_id:
                        await ws_manager.broadcast_progress(
                            document_id, "case_law_research", current_progress,
                            f"🔍 Wzbogacam {len(all_terms)} terminów o tłumaczenia z baz HUDOC, CURIA i IATE..."
                        )
                    logger.info(f"Enriching {len(all_terms)} terms with case law research")
                    all_terms = await researcher.enrich_terms(all_terms, document_id=document_id, ws_manager=ws_manager, current_progress=current_progress)
                    logger.info("Terms enriched with case law references")
            except Exception as e:
                logger.error(f"Error enriching terms with case law: {e}")
                # Continue with unenriched terms

        return all_terms

    async def _extract_from_segment(
        self, segment_text: str, section_type: str, known_terms_text: str
    ) -> List[Dict[str, Any]]:
        """
        Ekstrahuje terminy z pojedynczego segmentu.

        Args:
            segment_text: Tekst segmentu
            section_type: Typ sekcji
            known_terms_text: Sformatowany tekst znanych terminów

        Returns:
            Lista terminów
        """
        try:
            prompt = self.TERM_EXTRACTOR_PROMPT.format(
                segment_text=segment_text,
                section_type=section_type,
                known_terms=known_terms_text or "Brak znanych terminów",
            )

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parsuj odpowiedź JSON
            result = json.loads(response.content[0].text)
            terms = result.get("terms", [])

            # Waliduj i normalizuj terminy
            validated_terms = []
            for term in terms:
                if self._validate_term(term):
                    validated_terms.append(term)

            return validated_terms

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return []

    def _format_known_terms(self, known_terms: List[Dict[str, str]]) -> str:
        """
        Formatuje znane terminy do przekazania w prompcie.

        Args:
            known_terms: Lista znanych terminów

        Returns:
            Sformatowany tekst
        """
        if not known_terms:
            return ""

        lines = []
        for term in known_terms[:20]:  # Ogranicz do 20 terminów
            source = term.get("source", "")
            target = term.get("target", "")
            if source and target:
                lines.append(f"- {source} → {target}")

        return "\n".join(lines)

    def _validate_term(self, term: Dict[str, Any]) -> bool:
        """
        Waliduje ekstrahowany termin.

        Args:
            term: Słownik z informacją o terminie

        Returns:
            True jeśli termin jest poprawny
        """
        required_fields = ["source_term", "proposed_translation"]

        # Sprawdź czy wszystkie wymagane pola są obecne
        for field in required_fields:
            if field not in term or not term[field]:
                return False

        # Sprawdź długość
        if (
            len(term["source_term"]) < 2
            or len(term["source_term"]) > 200
            or len(term["proposed_translation"]) < 2
            or len(term["proposed_translation"]) > 200
        ):
            return False

        # Ustaw domyślne wartości
        term.setdefault("confidence", 0.6)
        term.setdefault("term_type", "other")
        term.setdefault("context", "")

        return True

    def get_terms_by_type(self, terms: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        Grupuje terminy według typu.

        Args:
            terms: Lista terminów

        Returns:
            Słownik z terminami pogrupowanymi według typu
        """
        grouped = {}
        for term in terms:
            term_type = term.get("term_type", "other")
            if term_type not in grouped:
                grouped[term_type] = []
            grouped[term_type].append(term)

        return grouped

    def get_high_confidence_terms(
        self, terms: List[Dict[str, Any]], threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Filtruje terminy o wysokim confidence.

        Args:
            terms: Lista terminów
            threshold: Minimalny próg confidence

        Returns:
            Lista terminów o wysokim confidence
        """
        return [term for term in terms if term.get("confidence", 0.0) >= threshold]

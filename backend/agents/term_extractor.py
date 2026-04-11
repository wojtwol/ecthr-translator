"""Term Extractor - ekstrahuje terminy prawnicze z tekstu."""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_case_law_researcher = None


class TermExtractor:
    """Ekstrahuje terminy prawnicze z segmentów."""

    TERM_EXTRACTOR_PROMPT = """Jesteś ekspertem w terminologii prawniczej ETPCz z głęboką znajomością Europejskiej Konwencji Praw Człowieka (EKPC).

=== ZASADY FUNDAMENTALNE ===

CRITICAL: Extract and suggest translations ONLY for terms that are actually present in the segment.
DO NOT invent, add, or infer any terms or context that are not in the source text.

1. SPÓJNOŚĆ TERMINOLOGICZNA - jeden termin źródłowy = jeden ekwiwalent docelowy
2. PRIORYTET EKPC - stosuj terminologię z oficjalnego tłumaczenia Konwencji
3. WYKRYWANIE WARIANTÓW - flaguj niespójności terminologiczne
4. UTARTE FORMUŁY - rozpoznawaj standardowe sformułowania ETPCz

Przeanalizuj poniższy segment orzeczenia ETPCz i zidentyfikuj wszystkie terminy prawnicze,
które wymagają spójnego tłumaczenia:

Segment:
{segment_text}

Typ sekcji: {section_type}

Znane terminy z pamięci tłumaczeniowej:
{known_terms}

Zidentyfikuj NOWE terminy (nie obecne w pamięci tłumaczeniowej) i zaproponuj polskie ekwiwalenty.

=== PRIORYTETY EKSTRAKCJI ===

Skup się na (w kolejności ważności):
1. TERMINOLOGIA EKPC - terminy z Konwencji mają najwyższy priorytet
2. Terminy specyficzne dla ETPCz (margin of appreciation, just satisfaction, etc.)
3. Terminy proceduralne (applicant, respondent Government, etc.)
4. Nazwy artykułów Konwencji i Protokołów
5. Łacińskie maksymy prawnicze
6. PEŁNE nazwy sądów i instytucji

=== ODNIESIENIA DO AKTÓW PRAWNYCH ===

Wykrywaj i standaryzuj odniesienia:
- EKPC: użyj formatu "art. X ust. Y Konwencji" (nie "§")
- Regulamin: użyj formatu "Reguła X § Y Regulaminu Trybunału"
- Paragrafy: "paragraf X" (nie "ustęp", nie "punkt")

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
5. NO DUPLICATES - each unique pair (source_term → proposed_translation) should appear ONLY ONCE in your response, even if the term appears multiple times in the segment with different contexts

CRITICAL: DO NOT EXTRACT PERSONAL NAMES!
- DO NOT extract first names (e.g., "John", "Maria", "Andrzej")
- DO NOT extract surnames (e.g., "Smith", "Kowalski", "Nowak")
- DO NOT extract full names of individuals (e.g., "Jan Kowalski", "John Smith")
- DO NOT extract names of applicants, lawyers, judges, or any other persons
- Names of persons are NOT terminology and should NEVER be included
- EXCEPTION: You CAN extract names of COURTS and INSTITUTIONS (e.g., "Warsaw Court of Appeal")

CRITICAL RULES FOR COURT/INSTITUTION NAMES:
6. Extract FULL names of courts and institutions, NOT individual words
   ✓ CORRECT: "Warsaw Court of Appeal" → "Sąd Apelacyjny w Warszawie"
   ✗ WRONG: "Appeal" alone (missing context - which appeal?)
   ✓ CORRECT: "Supreme Court" → "Sąd Najwyższy"
   ✗ WRONG: "Court" alone (missing which court)
   ✓ CORRECT: "District Court of Warsaw" → "Sąd Rejonowy w Warszawie"
   ✗ WRONG: "District Court" without location

7. For proper names of institutions, extract the complete official name:
   ✓ "European Court of Human Rights"
   ✓ "Constitutional Tribunal"
   ✓ "National Council of the Judiciary"
   ✗ NOT: "Tribunal" alone
   ✗ NOT: "Council" alone

CRITICAL RULES FOR CONTEXT-DEPENDENT TERMS:
8. The SAME word can have DIFFERENT translations depending on context!
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

9. ALWAYS include rich context showing HOW the term is used:
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

    def __init__(self, enable_case_law_research: bool = True, tm_manager=None):
        """
        Inicjalizacja Term Extractor.

        Args:
            enable_case_law_research: Czy włączyć wzbogacanie terminów z baz orzeczeń
            tm_manager: Shared TM manager instance to pass to CaseLawResearcher
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.extracted_terms_cache = {}  # Cache dla już wyekstrahowanych terminów
        self.enable_case_law_research = enable_case_law_research
        self.case_law_researcher = None
        self._shared_tm_manager = tm_manager
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
            self.case_law_researcher = CaseLawResearcher(tm_manager=self._shared_tm_manager)

        return self.case_law_researcher

    async def extract(
        self,
        segments: List[Dict[str, Any]],
        known_terms: Optional[List[Dict[str, str]]] = None,
        document_id: Optional[str] = None,
        ws_manager = None,
        current_progress: float = 0.5,
        all_segments: Optional[List[Dict[str, Any]]] = None,
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

        # Clear cache for each new extraction run (new document or new batch set)
        self.extracted_terms_cache = {}

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

                    # Deduplicate by source_term only — one term = one translation
                    # This ensures consistency: "Harju County Court" always gets
                    # the same Polish translation regardless of context
                    term_key = term["source_term"].lower().strip()

                    if term_key not in self.extracted_terms_cache:
                        self.extracted_terms_cache[term_key] = term
                        all_terms.append(term)

                logger.debug(f"Segment {i}: extracted {len(terms)} terms")

            except Exception as e:
                logger.error(f"Error extracting terms from segment {i}: {e}")

        logger.info(f"Extracted {len(all_terms)} unique terms from {len(segments)} segments")

        # Filter by frequency — min 2 occurrences in full document
        frequency_segments = all_segments if all_segments is not None else segments
        all_terms = self._filter_by_frequency(all_terms, frequency_segments, min_occurrences=2)

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
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parsuj odpowiedź JSON (obsługa markdown code blocks)
            raw_text = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                # Remove opening fence (```json or ```)
                first_newline = raw_text.index("\n")
                raw_text = raw_text[first_newline + 1:]
                # Remove closing fence
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3].strip()

            # Use JSONDecoder to handle extra text after JSON
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(raw_text)
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
        for term in known_terms[:100]:  # Ogranicz do 100 terminów
            source = term.get("source", "")
            target = term.get("target", "")
            if source and target:
                lines.append(f"- {source} → {target}")

        return "\n".join(lines)

    def _filter_by_frequency(
        self,
        terms: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
        min_occurrences: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Filter out terms that appear fewer than min_occurrences times in the document.

        Terms of type convention, latin, court_name, institution are exempt.
        """
        if not terms:
            return terms

        # Build full document text (lowercase) from all segments
        full_text = " ".join(
            seg.get("text", "") for seg in segments
        ).lower()

        exempt_types = {"convention", "latin", "court_name", "institution"}
        filtered = []
        removed_count = 0

        for term in terms:
            term_type = term.get("term_type", "other")
            if term_type in exempt_types:
                filtered.append(term)
                continue

            source = term.get("source_term", "").lower()
            if not source:
                continue

            count = full_text.count(source)
            if count >= min_occurrences:
                filtered.append(term)
            else:
                removed_count += 1
                logger.debug(
                    f"Filtered out term '{term.get('source_term')}' "
                    f"(occurrences: {count}, min: {min_occurrences})"
                )

        if removed_count:
            logger.info(
                f"Frequency filter: kept {len(filtered)}/{len(terms)} terms "
                f"(removed {removed_count} with <{min_occurrences} occurrences)"
            )

        return filtered

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

        # Odfiltruj imiona i nazwiska (1-2 słowa, obie z wielkiej litery, bez słów kluczowych)
        source = term["source_term"].strip()

        # Odfiltruj jednostki redakcyjne przepisów — to nie są terminy
        _LEGAL_PROVISION_RE = re.compile(
            r'^(article|art\.?|section|rule|paragraph|para\.?|'
            r'protocol(\s+no\.?)?|annex|schedule|chapter|part|regulation|'
            r'§)\s*\d',
            re.IGNORECASE
        )
        if _LEGAL_PROVISION_RE.match(source):
            logger.debug(f"Rejected legal provision reference: {source}")
            return False
        words = source.split()

        # Heurystyka: 1-2 słowa, każde zaczyna się wielką literą = prawdopodobnie imię/nazwisko
        if len(words) <= 2:
            # Wszystkie słowa zaczynają się wielką literą
            all_capitalized = all(w[0].isupper() for w in words if w)

            # Nie zawiera słów kluczowych instytucji/sądów
            institution_keywords = {
                'court', 'tribunal', 'ministry', 'office', 'commission', 'committee',
                'council', 'assembly', 'parliament', 'government', 'authority',
                'sąd', 'trybunał', 'ministerstwo', 'urząd', 'komisja', 'rada',
                'sejm', 'senat', 'rząd', 'prokuratura', 'rzecznik'
            }
            has_institution_keyword = any(
                kw in source.lower() for kw in institution_keywords
            )

            # Jeśli to 1-2 słowa z wielkiej litery bez słów kluczowych instytucji
            # to prawdopodobnie imię/nazwisko - odrzuć
            if all_capitalized and not has_institution_keyword:
                logger.debug(f"Rejected potential personal name: {source}")
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

"""Change Implementer - wdraża zatwierdzone zmiany terminów do tłumaczenia."""

import logging
from typing import List, Dict, Any
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)


class ChangeImplementer:
    """
    Agent odpowiedzialny za reimplementację zatwierdzonych terminów w tłumaczeniu.

    Po walidacji użytkownik może:
    - Zatwierdzić termin (approved) - bez zmian
    - Edytować termin (edited) - z poprawką
    - Odrzucić termin (rejected) - wymaga ręcznego tłumaczenia

    Change Implementer aktualizuje tłumaczenie zgodnie z decyzjami użytkownika.
    """

    def __init__(self, api_key: str = None):
        """
        Inicjalizacja Change Implementer.

        Args:
            api_key: Klucz API Anthropic (opcjonalny, domyślnie z settings)
        """
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        logger.info("Change Implementer initialized")

    async def implement_changes(
        self,
        segments: List[Dict[str, Any]],
        validated_terms: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Implementuje zatwierdzone zmiany terminów w tłumaczonych segmentach.

        Args:
            segments: Segmenty z tłumaczeniami
            validated_terms: Zatwierdzone terminy z walidacji

        Returns:
            Zaktualizowane segmenty z poprawionymi terminami
        """
        try:
            logger.info(f"Implementing changes for {len(validated_terms)} terms")

            # Separate approved/edited terms from rejected terms
            approved_terms = [
                t for t in validated_terms
                if t.get("status") in ["approved", "edited"]
            ]

            rejected_terms = [
                t for t in validated_terms
                if t.get("status") == "rejected"
            ]

            logger.info(f"Found {len(approved_terms)} approved/edited terms, {len(rejected_terms)} rejected terms")

            if not approved_terms and not rejected_terms:
                logger.info("No terms to implement or avoid")
                return segments

            # Stwórz mapowanie source_term -> target_term dla zatwierdzonych terminów
            terminology_map = {}
            for term in approved_terms:
                source_term = term.get("source_term", "")
                target_term = term.get("target_term", "")
                if source_term and target_term:
                    terminology_map[source_term] = target_term

            # Grupuj terminy według kontekstu dla efektywnego przetwarzania
            updated_segments = []

            def term_matches_segment(source_term: str, source_text_lower: str) -> bool:
                """Check if a term matches the segment text (handles parenthetical variations)."""
                if not source_term:
                    return False

                term_lower = source_term.lower()

                # Direct match
                if term_lower in source_text_lower:
                    return True

                # Try matching without parenthetical content
                # e.g., "Chief Justice (Magistrato Dirigente)" -> "Chief Justice"
                import re
                term_without_parens = re.sub(r'\s*\([^)]*\)', '', term_lower).strip()
                if term_without_parens and term_without_parens in source_text_lower:
                    return True

                # Try matching the main term (before any parenthesis)
                main_term = term_lower.split('(')[0].strip()
                if main_term and len(main_term) > 2 and main_term in source_text_lower:
                    return True

                return False

            for segment in segments:
                # Check if segment contains any approved OR rejected terms
                source_text = segment.get("source_text", "")
                source_text_lower = source_text.lower()

                relevant_approved = []
                relevant_rejected = []

                for term in approved_terms:
                    source_term = term.get("source_term", "")
                    if term_matches_segment(source_term, source_text_lower):
                        relevant_approved.append(term)

                for term in rejected_terms:
                    source_term = term.get("source_term", "")
                    if term_matches_segment(source_term, source_text_lower):
                        relevant_rejected.append(term)

                # Re-translate if segment contains approved OR rejected terms
                if relevant_approved or relevant_rejected:
                    logger.info(f"Re-translating segment with {len(relevant_approved)} approved terms, {len(relevant_rejected)} rejected terms")
                    updated_text = await self._retranslate_segment(
                        source_text,
                        relevant_approved,
                        segment.get("translated_text", ""),
                        rejected_terms=relevant_rejected
                    )

                    updated_segment = segment.copy()
                    updated_segment["translated_text"] = updated_text
                    updated_segment["change_implemented"] = True
                    updated_segments.append(updated_segment)
                else:
                    # Segment bez zmian
                    updated_segments.append(segment)

            logger.info(f"Changes implemented in {len(updated_segments)} segments")
            return updated_segments

        except Exception as e:
            logger.error(f"Error implementing changes: {e}", exc_info=True)
            # W przypadku błędu zwróć oryginalne segmenty
            return segments

    async def _retranslate_segment(
        self,
        source_text: str,
        terms: List[Dict[str, Any]],
        original_translation: str = "",
        rejected_terms: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Re-translates a segment with approved terminology and avoiding rejected terms.

        This is more reliable than trying to replace terms in existing translation,
        because it handles grammatical forms, context, and ensures terminology is used.

        Args:
            source_text: English source text
            terms: List of approved terms to use
            original_translation: Original Polish translation (for reference)
            rejected_terms: List of rejected terms to avoid

        Returns:
            New Polish translation with approved terminology
        """
        try:
            # Build terminology table for approved terms
            terminology_lines = []
            for term in terms:
                source_term = term.get("source_term", "")
                target_term = term.get("target_term", "")
                if source_term and target_term:
                    terminology_lines.append(f"- {source_term} → {target_term}")

            terminology_text = "\n".join(terminology_lines) if terminology_lines else "Brak zatwierdzonych terminów"

            # Build list of rejected terms (to avoid)
            rejected_lines = []
            if rejected_terms:
                for term in rejected_terms:
                    source_term = term.get("source_term", "")
                    # Include original proposal that was rejected
                    original_proposal = term.get("original_proposal", term.get("target_term", ""))
                    if source_term and original_proposal:
                        rejected_lines.append(f"- {source_term} → NIE UŻYWAJ: {original_proposal}")

            rejected_text = "\n".join(rejected_lines) if rejected_lines else ""

            # Build the rejected terms section
            rejected_section = ""
            if rejected_text:
                rejected_section = f"""

REJECTED TERMINOLOGY (DO NOT USE - find alternative translations):
{rejected_text}
"""

            # Prompt for Claude to translate with approved terminology
            prompt = f"""You are a professional legal translator (English to Polish).

CRITICAL: Translate ONLY what is in the source text. DO NOT add, invent, or infer any information.

Translate the following English text to Polish, using the APPROVED TERMINOLOGY provided below.

SOURCE TEXT (EN):
{source_text}

APPROVED TERMINOLOGY (MUST USE):
{terminology_text}
{rejected_section}
INSTRUCTIONS:
1. Use the approved Polish terms for the English terms listed above - these are MANDATORY
2. For rejected terms: find appropriate alternative translations (do NOT use the rejected translations)
3. Apply proper Polish grammar and declension (cases, gender, etc.)
4. Maintain professional legal language style
5. Ensure the translation is natural and fluent
6. The approved terminology MUST be used - do not substitute with synonyms

CRITICAL RULES:
1. Translate ONLY the source text provided above - nothing more, nothing less
2. DO NOT add dates, facts, or events that are not in the source
3. DO NOT infer or complete incomplete information
4. DO NOT add explanations, interpretations, or context
5. If the source is incomplete or unclear, translate it as-is
6. Paragraph numbers like [35], [36] are part of the source - keep them exactly

ECHR TERMINOLOGY RULES:
- Registrar = Kanclerz (NEVER "Sekretarz")
- Section Registrar = Kanclerz Sekcji (NEVER "Sekretarz Sekcji")
- Registry = Kancelaria Trybunału
- alleged violation = zarzucane naruszenie / zarzut naruszenia (NEVER "domniemane naruszenie")
- Use Polish quotation marks: „..." (opening „ U+201E, closing " U+201D)
- Defined terms in parentheses: nominative case with capital letter, e.g. („Konwencja"), („Rząd")
- EKPC references: use "ust." NOT "§" (e.g. art. 8 ust. 1 Konwencji)
- Regulamin references: use "§" (e.g. Reguła 77 § 1 Regulaminu Trybunału)
- Paragraphs of current judgment: spell out "paragraf" (e.g. paragraf 34)
- Paragraphs of cited judgments: use "§" symbol (e.g. § 34)
- Polish court names: use official names with proper capitalization
  (names may include "dla" or "w" depending on the specific court)
- Do NOT put a comma inside prepositional phrases starting a sentence:
  ✓ "W przypadku gdy..." ✗ "W przypadku, gdy..."

IMPORTANT: Return ONLY the Polish translation, without any explanations or notes."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for consistency
                messages=[{"role": "user", "content": prompt}],
            )

            updated_text = response.content[0].text.strip()

            logger.debug(f"Re-translated segment with {len(terms)} approved terms")
            return updated_text

        except Exception as e:
            logger.error(f"Error re-translating segment: {e}", exc_info=True)
            # Fallback to original translation
            return original_translation

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki Change Implementer.

        Returns:
            Słownik ze statystykami
        """
        return {
            "status": "active",
            "model": self.model,
        }

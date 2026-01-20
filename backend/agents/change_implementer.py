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

            # FIXED: Aplikuj WSZYSTKIE zatwierdzone i edytowane terminy, nie tylko edited
            # Użytkownik zatwierdza termin = chce go użyć w tłumaczeniu
            approved_terms = [
                t for t in validated_terms
                if t.get("status") in ["approved", "edited"]
            ]

            if not approved_terms:
                logger.info("No approved or edited terms to implement")
                return segments

            logger.info(f"Found {len(approved_terms)} approved/edited terms to implement")

            # Stwórz mapowanie source_term -> target_term dla zatwierdzonych terminów
            terminology_map = {}
            for term in approved_terms:
                source_term = term.get("source_term", "")
                target_term = term.get("target_term", "")
                if source_term and target_term:
                    terminology_map[source_term] = target_term

            # Grupuj terminy według kontekstu dla efektywnego przetwarzania
            updated_segments = []

            for segment in segments:
                # FIXED: Sprawdź czy segment zawiera jakieś zatwierdzone terminy
                # w ANGIELSKIM TEKŚCIE ŹRÓDŁOWYM (source_text), nie w polskim tłumaczeniu
                source_text = segment.get("source_text", "")
                source_text_lower = source_text.lower()
                relevant_terms = []

                for term in approved_terms:
                    # Sprawdź czy angielski termin występuje w angielskim źródle
                    source_term = term.get("source_term", "")
                    if source_term and source_term.lower() in source_text_lower:
                        relevant_terms.append(term)

                if relevant_terms:
                    # Segment wymaga aktualizacji - przetłumacz ponownie z zatwierdzoną terminologią
                    logger.info(f"Re-translating segment with {len(relevant_terms)} approved terms")
                    updated_text = await self._retranslate_segment(
                        source_text,
                        relevant_terms,
                        segment.get("translated_text", "")
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
    ) -> str:
        """
        Re-translates a segment with approved terminology.

        This is more reliable than trying to replace terms in existing translation,
        because it handles grammatical forms, context, and ensures terminology is used.

        Args:
            source_text: English source text
            terms: List of approved terms to use
            original_translation: Original Polish translation (for reference)

        Returns:
            New Polish translation with approved terminology
        """
        try:
            # Build terminology table for prompt
            terminology_lines = []
            for term in terms:
                source_term = term.get("source_term", "")
                target_term = term.get("target_term", "")
                if source_term and target_term:
                    terminology_lines.append(f"- {source_term} → {target_term}")

            terminology_text = "\n".join(terminology_lines)

            # Prompt for Claude to translate with approved terminology
            prompt = f"""You are a professional legal translator (English to Polish).

CRITICAL: Translate ONLY what is in the source text. DO NOT add, invent, or infer any information.

Translate the following English text to Polish, using the APPROVED TERMINOLOGY provided below.

SOURCE TEXT (EN):
{source_text}

APPROVED TERMINOLOGY (MUST USE):
{terminology_text}

INSTRUCTIONS:
1. Use the approved Polish terms for the English terms listed above
2. Apply proper Polish grammar and declension (cases, gender, etc.)
3. Maintain professional legal language style
4. Ensure the translation is natural and fluent
5. The approved terminology MUST be used - do not substitute with synonyms

CRITICAL RULES:
1. Translate ONLY the source text provided above - nothing more, nothing less
2. DO NOT add dates, facts, or events that are not in the source
3. DO NOT infer or complete incomplete information
4. DO NOT add explanations, interpretations, or context
5. If the source is incomplete or unclear, translate it as-is
6. Paragraph numbers like [35], [36] are part of the source - keep them exactly

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

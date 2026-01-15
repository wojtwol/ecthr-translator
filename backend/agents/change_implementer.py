"""Change Implementer - wdraża zatwierdzone zmiany terminów do tłumaczenia."""

import logging
import re
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
        self.model = "claude-3-5-sonnet-20241022"
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

            # Filtruj tylko terminy edytowane (zmienione przez użytkownika)
            edited_terms = [
                t for t in validated_terms
                if t.get("status") == "edited" and t.get("original_proposal") != t.get("target_term")
            ]

            if not edited_terms:
                logger.info("No edited terms to implement")
                return segments

            logger.info(f"Found {len(edited_terms)} edited terms to implement")

            # Grupuj terminy według kontekstu dla efektywnego przetwarzania
            updated_segments = []

            for segment in segments:
                # Sprawdź czy segment zawiera jakieś edytowane terminy
                segment_text = segment.get("translated_text", "")
                relevant_terms = []

                for term in edited_terms:
                    # Sprawdź czy oryginalny termin (przed edycją) występuje w tym segmencie
                    original = term.get("original_proposal", "")
                    if original and original.lower() in segment_text.lower():
                        relevant_terms.append(term)

                if relevant_terms:
                    # Segment wymaga aktualizacji
                    updated_text = await self._update_segment(
                        segment_text,
                        relevant_terms,
                        segment.get("source_text", "")
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

    async def _update_segment(
        self,
        translated_text: str,
        terms: List[Dict[str, Any]],
        source_text: str = "",
    ) -> str:
        """
        Aktualizuje pojedynczy segment z uwzględnieniem edytowanych terminów.

        Args:
            translated_text: Oryginalne tłumaczenie
            terms: Lista edytowanych terminów do wdrożenia
            source_text: Tekst źródłowy (dla kontekstu)

        Returns:
            Zaktualizowany tekst tłumaczenia
        """
        try:
            # Przygotuj listę zmian dla Claude
            changes_list = []
            for term in terms:
                changes_list.append(
                    f"- Replace '{term['original_proposal']}' with '{term['target_term']}'"
                )

            changes_text = "\n".join(changes_list)

            # Prompt dla Claude do inteligentnej implementacji zmian
            prompt = f"""You are a professional translator implementing terminology corrections.

SOURCE TEXT (EN):
{source_text}

CURRENT TRANSLATION (PL):
{translated_text}

TERMINOLOGY CORRECTIONS TO IMPLEMENT:
{changes_text}

INSTRUCTIONS:
1. Replace the old terms with the new approved terms
2. Ensure proper grammar and declension after changes
3. Maintain the overall sentence structure and meaning
4. Handle cases where the term appears in different grammatical forms
5. Be careful to only change the specific terms, not similar words

Return ONLY the corrected Polish translation, without any explanations."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for more consistent changes
                messages=[{"role": "user", "content": prompt}],
            )

            updated_text = response.content[0].text.strip()

            logger.debug(f"Updated segment: {translated_text[:50]}... -> {updated_text[:50]}...")
            return updated_text

        except Exception as e:
            logger.error(f"Error updating segment: {e}", exc_info=True)
            # W przypadku błędu, spróbuj prostej zamiany
            return self._simple_replace(translated_text, terms)

    def _simple_replace(
        self,
        text: str,
        terms: List[Dict[str, Any]],
    ) -> str:
        """
        Prosta zamiana terminów jako fallback.

        Args:
            text: Tekst do aktualizacji
            terms: Terminy do zamiany

        Returns:
            Zaktualizowany tekst
        """
        updated_text = text

        for term in terms:
            old_term = term.get("original_proposal", "")
            new_term = term.get("target_term", "")

            if old_term and new_term:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(old_term), re.IGNORECASE)
                updated_text = pattern.sub(new_term, updated_text)

        return updated_text

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

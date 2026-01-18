"""Translator - tłumaczy segmenty z wykorzystaniem terminologii."""

import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)


class Translator:
    """Tłumaczy segmenty orzeczeń ETPCz."""

    TRANSLATOR_PROMPT = """Jesteś profesjonalnym tłumaczem prawniczym specjalizującym się w orzeczeniach ETPCz.

Przetłumacz poniższy segment na język polski, zachowując:
- Styl i rejestr orzeczeń sądowych
- Spójność terminologiczną (użyj TYLKO podanych ekwiwalentów)
- Strukturę zdań typową dla polskiego języka prawniczego

Segment do tłumaczenia:
{source_text}

Typ sekcji: {section_type}

OBOWIĄZKOWA TERMINOLOGIA (użyj dokładnie tych ekwiwalentów):
{terminology_table}

Kontekst (poprzednie przetłumaczone segmenty):
{context}

Przetłumacz segment. Nie dodawaj żadnych komentarzy ani wyjaśnień. Zwróć tylko tłumaczenie."""

    def __init__(self, on_segment_translated=None):
        """Inicjalizacja Translator.

        Args:
            on_segment_translated: Optional callback called after each segment translation
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.translation_context = []  # Kontekst ostatnich tłumaczeń
        self.on_segment_translated = on_segment_translated
        logger.info("Translator initialized")

    async def translate(
        self,
        segments: List[Dict[str, Any]],
        terminology: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Tłumaczy segmenty z wykorzystaniem terminologii.

        Args:
            segments: Lista segmentów do przetłumaczenia
            terminology: Słownik terminologii {source: target}

        Returns:
            Lista przetłumaczonych segmentów
        """
        translated_segments = []
        self.translation_context = []

        for i, segment in enumerate(segments):
            try:
                source_text = segment.get("text", "")

                # Pomiń puste segmenty
                if not source_text.strip():
                    segment["target_text"] = ""
                    translated_segments.append(segment)
                    continue

                # Tłumacz segment
                target_text = await self._translate_segment(
                    source_text=source_text,
                    section_type=segment.get("section_type", "OTHER"),
                    terminology=terminology,
                )

                # Dodaj tłumaczenie
                segment["target_text"] = target_text
                translated_segments.append(segment)

                # Aktualizuj kontekst (ostatnie 3 segmenty)
                self.translation_context.append(
                    {"source": source_text, "target": target_text}
                )
                if len(self.translation_context) > 3:
                    self.translation_context.pop(0)

                logger.debug(
                    f"Segment {i} translated: {source_text[:50]}... -> {target_text[:50]}..."
                )

                # Callback dla live updates
                if self.on_segment_translated:
                    try:
                        await self.on_segment_translated(i, len(segments), segment)
                    except Exception as e:
                        logger.error(f"Error in segment callback: {e}")

            except Exception as e:
                logger.error(f"Error translating segment {i}: {e}", exc_info=True)
                segment["target_text"] = f"[BŁĄD TŁUMACZENIA: {source_text}]"
                translated_segments.append(segment)

        logger.info(f"Translation loop completed - {len(translated_segments)} segments processed")
        logger.info(f"Preparing to return {len(translated_segments)} segments to orchestrator")
        return translated_segments

    async def _translate_segment(
        self,
        source_text: str,
        section_type: str,
        terminology: Dict[str, str],
    ) -> str:
        """
        Tłumaczy pojedynczy segment.

        Args:
            source_text: Tekst do przetłumaczenia
            section_type: Typ sekcji
            terminology: Słownik terminologii

        Returns:
            Przetłumaczony tekst
        """
        # Przygotuj tabelę terminologii
        terminology_table = self._format_terminology(terminology, source_text)

        # Przygotuj kontekst
        context_text = self._format_context()

        # Zbuduj prompt
        prompt = self.TRANSLATOR_PROMPT.format(
            source_text=source_text,
            section_type=section_type,
            terminology_table=terminology_table or "Brak terminologii",
            context=context_text or "Brak kontekstu",
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Sonnet 4.5 dla jakości tłumaczenia
                max_tokens=2000,
                temperature=0.3,  # Niska temperatura dla konsystencji
                messages=[{"role": "user", "content": prompt}],
            )

            translation = response.content[0].text.strip()

            # Waliduj tłumaczenie
            if not translation or len(translation) < 3:
                logger.warning(f"Translation too short, using fallback")
                return f"[WYMAGANE TŁUMACZENIE RĘCZNE: {source_text}]"

            return translation

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"[BŁĄD API: {source_text}]"

    def _format_terminology(
        self, terminology: Dict[str, str], source_text: str
    ) -> str:
        """
        Formatuje terminologię dla promptu.

        Args:
            terminology: Słownik terminologii
            source_text: Tekst źródłowy (dla filtrowania)

        Returns:
            Sformatowana tabela terminologii
        """
        if not terminology:
            return ""

        # Filtruj tylko terminy występujące w tym segmencie
        relevant_terms = {}
        source_lower = source_text.lower()

        for source_term, target_term in terminology.items():
            if source_term.lower() in source_lower:
                relevant_terms[source_term] = target_term

        # Jeśli nie ma relevantnych terminów, zwróć pusty string
        if not relevant_terms:
            return ""

        # Zbuduj tabelę
        lines = []
        for source_term, target_term in relevant_terms.items():
            lines.append(f"| {source_term} | {target_term} |")

        return "\n".join(lines)

    def _format_context(self) -> str:
        """
        Formatuje kontekst dla promptu.

        Returns:
            Sformatowany kontekst
        """
        if not self.translation_context:
            return ""

        lines = []
        for item in self.translation_context[-3:]:  # Ostatnie 3 segmenty
            lines.append(f"EN: {item['source']}")
            lines.append(f"PL: {item['target']}")
            lines.append("")

        return "\n".join(lines)

    async def translate_single(
        self, text: str, terminology: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Tłumaczy pojedynczy tekst (utility function).

        Args:
            text: Tekst do przetłumaczenia
            terminology: Opcjonalna terminologia

        Returns:
            Przetłumaczony tekst
        """
        terminology = terminology or {}
        return await self._translate_segment(
            source_text=text, section_type="OTHER", terminology=terminology
        )

    def get_translation_stats(
        self, segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Zwraca statystyki tłumaczenia.

        Args:
            segments: Lista przetłumaczonych segmentów

        Returns:
            Słownik ze statystykami
        """
        total = len(segments)
        translated = sum(
            1
            for s in segments
            if s.get("target_text")
            and not s["target_text"].startswith("[BŁĄD")
            and not s["target_text"].startswith("[WYMAGANE")
        )
        errors = sum(
            1
            for s in segments
            if s.get("target_text", "").startswith(("[BŁĄD", "[WYMAGANE"))
        )

        return {
            "total_segments": total,
            "translated": translated,
            "errors": errors,
            "success_rate": translated / total if total > 0 else 0.0,
        }

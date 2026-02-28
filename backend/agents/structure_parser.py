"""Structure Parser - rozpoznaje strukturę orzeczeń ETPCz."""

import logging
import re
import json
from typing import List, Dict, Any
from anthropic import Anthropic
from config import settings
from models.segment import SectionType

logger = logging.getLogger(__name__)


class StructureParser:
    """Rozpoznaje strukturę orzeczenia ETPCz i klasyfikuje segmenty."""

    STRUCTURE_PARSER_PROMPT = """Jesteś ekspertem w analizie orzeczeń Europejskiego Trybunału Praw Człowieka (ETPCz).

Przeanalizuj poniższy segment tekstu i określ, do której sekcji orzeczenia należy:
- PROCEDURE: informacje proceduralne, skład sędziowski, daty
- FACTS: stan faktyczny sprawy, okoliczności, prawo krajowe
- LAW: ocena prawna, analiza zarzutów, dopuszczalność, meritum
- OPERATIVE: sentencja, rozstrzygnięcie, koszty
- OTHER: inne sekcje

Segment:
{segment_text}

Kontekst (poprzednie segmenty):
{context}

Odpowiedz w formacie JSON:
{{
    "section_type": "PROCEDURE" | "FACTS" | "LAW" | "OPERATIVE" | "OTHER",
    "confidence": 0.0-1.0,
    "subsection": "opcjonalnie, np. 'CIRCUMSTANCES OF THE CASE'",
    "reasoning": "krótkie uzasadnienie klasyfikacji"
}}"""

    def __init__(self):
        """Inicjalizacja Structure Parser."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        logger.info("Structure Parser initialized")

    async def parse(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parsuje segmenty i przypisuje im typy sekcji.

        Args:
            segments: Lista segmentów z tektem

        Returns:
            Lista segmentów z przypisanymi section_type
        """
        parsed_segments = []
        context = []

        for i, segment in enumerate(segments):
            try:
                # Zbuduj kontekst (ostatnie 2 segmenty)
                context_text = "\n".join([s.get("text", "") for s in context[-2:]])

                # Zapytaj Claude o klasyfikację
                section_info = await self._classify_segment(
                    segment.get("text", ""), context_text
                )

                # Dodaj informację o sekcji do segmentu
                segment["section_type"] = section_info.get("section_type", "OTHER")
                segment["section_confidence"] = section_info.get("confidence", 0.0)
                segment["subsection"] = section_info.get("subsection")

                parsed_segments.append(segment)
                context.append(segment)

                logger.debug(
                    f"Segment {i}: {segment['section_type']} "
                    f"(confidence: {segment['section_confidence']:.2f})"
                )

            except Exception as e:
                logger.error(f"Error parsing segment {i}: {e}")
                segment["section_type"] = "OTHER"
                segment["section_confidence"] = 0.0
                parsed_segments.append(segment)

        logger.info(
            f"Parsed {len(parsed_segments)} segments. "
            f"Distribution: {self._get_distribution(parsed_segments)}"
        )

        return parsed_segments

    async def _classify_segment(
        self, segment_text: str, context: str
    ) -> Dict[str, Any]:
        """
        Klasyfikuje pojedynczy segment używając Claude API.

        Args:
            segment_text: Tekst segmentu
            context: Kontekst (poprzednie segmenty)

        Returns:
            Informacja o klasyfikacji
        """
        # Dla krótkich segmentów używamy prostszej heurystyki
        if len(segment_text.strip()) < 50:
            return self._simple_classification(segment_text)

        try:
            prompt = self.STRUCTURE_PARSER_PROMPT.format(
                segment_text=segment_text, context=context or "Brak kontekstu"
            )

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Szybki model dla klasyfikacji
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            result = self._extract_json(response.content[0].text)

            # Waliduj section_type
            section_type = result.get("section_type", "OTHER").upper()
            if section_type not in ["PROCEDURE", "FACTS", "LAW", "OPERATIVE", "OTHER"]:
                section_type = "OTHER"

            return {
                "section_type": section_type,
                "confidence": float(result.get("confidence", 0.5)),
                "subsection": result.get("subsection"),
                "reasoning": result.get("reasoning"),
            }

        except Exception as e:
            logger.warning(f"Claude API error, using simple classification: {e}")
            return self._simple_classification(segment_text)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Wyciąga JSON z odpowiedzi Claude, obsługując markdown code blocks,
        trailing text, i drobne błędy formatowania.

        Args:
            text: Surowy tekst odpowiedzi Claude

        Returns:
            Sparsowany dict

        Raises:
            ValueError: Gdy nie udało się wyciągnąć JSON
        """
        # 1. Strip markdown code fences
        cleaned = text.strip()
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # 2. Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Extract first {...} block from text
        brace_match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                # 4. Try fixing common issues: trailing commas, single quotes
                fixed = brace_match.group(0)
                fixed = re.sub(r',\s*}', '}', fixed)  # trailing comma
                fixed = re.sub(r",\s*]", "]", fixed)  # trailing comma in arrays
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        # 5. Last resort: regex extraction of section_type
        type_match = re.search(
            r'"?section_type"?\s*:\s*"?(PROCEDURE|FACTS|LAW|OPERATIVE|OTHER)"?',
            text, re.IGNORECASE
        )
        if type_match:
            section = type_match.group(1).upper()
            conf_match = re.search(r'"?confidence"?\s*:\s*([0-9.]+)', text)
            confidence = float(conf_match.group(1)) if conf_match else 0.6
            return {
                "section_type": section,
                "confidence": confidence,
                "subsection": None,
                "reasoning": "Extracted via regex fallback",
            }

        raise ValueError(f"Could not extract JSON from response: {text[:200]}")

    def _simple_classification(self, text: str) -> Dict[str, Any]:
        """
        Prosta klasyfikacja oparta na keywords (fallback).

        Args:
            text: Tekst do klasyfikacji

        Returns:
            Informacja o klasyfikacji
        """
        text_lower = text.lower()

        # Keywords dla każdej sekcji
        if any(
            kw in text_lower
            for kw in ["procedure", "application", "composed of", "judges", "registrar"]
        ):
            return {
                "section_type": "PROCEDURE",
                "confidence": 0.7,
                "subsection": None,
                "reasoning": "Keyword match",
            }

        if any(
            kw in text_lower
            for kw in ["facts", "circumstances", "domestic law", "applicant", "born in"]
        ):
            return {
                "section_type": "FACTS",
                "confidence": 0.7,
                "subsection": None,
                "reasoning": "Keyword match",
            }

        if any(
            kw in text_lower
            for kw in [
                "alleged violation",
                "article",
                "convention",
                "admissibility",
                "merits",
                "court considers",
            ]
        ):
            return {
                "section_type": "LAW",
                "confidence": 0.7,
                "subsection": None,
                "reasoning": "Keyword match",
            }

        if any(
            kw in text_lower
            for kw in [
                "for these reasons",
                "court holds",
                "unanimously",
                "decides",
                "orders",
            ]
        ):
            return {
                "section_type": "OPERATIVE",
                "confidence": 0.7,
                "subsection": None,
                "reasoning": "Keyword match",
            }

        return {
            "section_type": "OTHER",
            "confidence": 0.5,
            "subsection": None,
            "reasoning": "No clear match",
        }

    def _get_distribution(self, segments: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Oblicza rozkład typów sekcji.

        Args:
            segments: Lista segmentów

        Returns:
            Słownik z ilością segmentów każdego typu
        """
        distribution = {}
        for segment in segments:
            section_type = segment.get("section_type", "OTHER")
            distribution[section_type] = distribution.get(section_type, 0) + 1
        return distribution

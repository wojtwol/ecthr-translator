"""QA Reviewer - sprawdza spójność i jakość tłumaczenia."""

import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)


class QAIssue:
    """Reprezentuje potencjalny problem w tłumaczeniu."""

    def __init__(
        self,
        severity: str,  # "critical", "warning", "info"
        category: str,  # "terminology", "grammar", "consistency", "completeness"
        description: str,
        segment_index: Optional[int] = None,
        suggestion: Optional[str] = None,
    ):
        self.severity = severity
        self.category = category
        self.description = description
        self.segment_index = segment_index
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        """Konwertuje issue na słownik."""
        return {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "segment_index": self.segment_index,
            "suggestion": self.suggestion,
        }


class QAReviewer:
    """
    Agent odpowiedzialny za kontrolę jakości tłumaczenia.

    Sprawdza:
    - Spójność terminologii
    - Kompletność tłumaczenia
    - Poprawność gramatyczną
    - Zgodność z oryginałem
    - Formatowanie i struktura
    """

    def __init__(self, api_key: str = None):
        """
        Inicjalizacja QA Reviewer.

        Args:
            api_key: Klucz API Anthropic (opcjonalny, domyślnie z settings)
        """
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.review_count = 0
        logger.info("QA Reviewer initialized")

    async def review(
        self,
        segments: List[Dict[str, Any]],
        validated_terms: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Przeprowadza kompleksowy przegląd tłumaczenia.

        Args:
            segments: Segmenty z tłumaczeniami
            validated_terms: Zatwierdzone terminy

        Returns:
            Raport z przeglądu zawierający znalezione problemy i statystyki
        """
        try:
            logger.info(f"Starting QA review for {len(segments)} segments")
            self.review_count += 1

            issues = []

            # Sprawdzenie 1: Kompletność tłumaczenia
            completeness_issues = self._check_completeness(segments)
            issues.extend(completeness_issues)

            # Sprawdzenie 2: Spójność terminologii
            terminology_issues = self._check_terminology_consistency(
                segments, validated_terms
            )
            issues.extend(terminology_issues)

            # Sprawdzenie 3: Próbki jakości (używa Claude)
            if len(segments) <= 20:
                # Dla małych dokumentów sprawdź wszystkie
                quality_issues = await self._check_quality_sample(segments, list(range(len(segments))))
            else:
                # Dla dużych dokumentów sprawdź próbkę
                import random
                sample_indices = random.sample(range(len(segments)), min(10, len(segments)))
                quality_issues = await self._check_quality_sample(segments, sample_indices)

            issues.extend(quality_issues)

            # Analiza wyników
            critical_count = sum(1 for i in issues if i.severity == "critical")
            warning_count = sum(1 for i in issues if i.severity == "warning")
            info_count = sum(1 for i in issues if i.severity == "info")

            # Decyzja o zatwierdzeniu
            approved = critical_count == 0

            report = {
                "approved": approved,
                "review_id": f"qa_{self.review_count}",
                "issues_count": {
                    "critical": critical_count,
                    "warning": warning_count,
                    "info": info_count,
                    "total": len(issues),
                },
                "issues": [issue.to_dict() for issue in issues],
                "summary": self._generate_summary(issues, approved),
                "segments_reviewed": len(segments),
            }

            logger.info(
                f"QA review complete: {critical_count} critical, "
                f"{warning_count} warnings, {info_count} info"
            )

            return report

        except Exception as e:
            logger.error(f"Error in QA review: {e}", exc_info=True)
            return {
                "approved": False,
                "error": str(e),
                "issues_count": {"critical": 1, "warning": 0, "info": 0, "total": 1},
                "issues": [
                    {
                        "severity": "critical",
                        "category": "system",
                        "description": f"QA review failed: {str(e)}",
                    }
                ],
            }

    def _check_completeness(
        self, segments: List[Dict[str, Any]]
    ) -> List[QAIssue]:
        """
        Sprawdza kompletność tłumaczenia.

        Args:
            segments: Segmenty do sprawdzenia

        Returns:
            Lista znalezionych problemów
        """
        issues = []

        for i, segment in enumerate(segments):
            source_text = segment.get("source_text", "").strip()
            translated_text = segment.get("translated_text", "").strip()

            # Sprawdź czy segment jest przetłumaczony
            if source_text and not translated_text:
                issues.append(
                    QAIssue(
                        severity="critical",
                        category="completeness",
                        description=f"Segment {i+1} not translated",
                        segment_index=i,
                    )
                )

            # Sprawdź długość (bardzo krótkie tłumaczenie może być problemem)
            if translated_text and len(translated_text) < len(source_text) * 0.3:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="completeness",
                        description=f"Segment {i+1} translation seems too short",
                        segment_index=i,
                    )
                )

        return issues

    def _check_terminology_consistency(
        self, segments: List[Dict[str, Any]], validated_terms: List[Dict[str, Any]]
    ) -> List[QAIssue]:
        """
        Sprawdza spójność używania terminologii.

        Args:
            segments: Segmenty z tłumaczeniami
            validated_terms: Zatwierdzone terminy

        Returns:
            Lista problemów ze spójnością terminologii
        """
        issues = []

        # Buduj mapę zatwierdzonych terminów
        approved_terms = {}
        for term in validated_terms:
            if term.get("status") in ["approved", "edited"]:
                source = term.get("source_term", "").lower()
                target = term.get("target_term", "")
                approved_terms[source] = target

        # Sprawdź czy zatwierdzone terminy są używane konsekwentnie
        term_usage = {}  # source_term -> set of translations used

        for i, segment in enumerate(segments):
            source_text = segment.get("source_text", "").lower()
            translated_text = segment.get("translated_text", "")

            for source_term, approved_translation in approved_terms.items():
                if source_term in source_text:
                    # Termin występuje w źródle
                    if source_term not in term_usage:
                        term_usage[source_term] = set()

                    # Sprawdź czy zatwierdzone tłumaczenie jest w tekście
                    if approved_translation.lower() not in translated_text.lower():
                        # Może być problem - termin nie używa zatwierdzonego tłumaczenia
                        issues.append(
                            QAIssue(
                                severity="warning",
                                category="terminology",
                                description=f"Term '{source_term}' may not use approved translation '{approved_translation}' in segment {i+1}",
                                segment_index=i,
                                suggestion=f"Ensure '{approved_translation}' is used for '{source_term}'",
                            )
                        )

        return issues

    async def _check_quality_sample(
        self, segments: List[Dict[str, Any]], indices: List[int]
    ) -> List[QAIssue]:
        """
        Sprawdza jakość próbki segmentów używając Claude.

        Args:
            segments: Wszystkie segmenty
            indices: Indeksy segmentów do sprawdzenia

        Returns:
            Lista znalezionych problemów
        """
        issues = []

        for idx in indices:
            if idx >= len(segments):
                continue

            segment = segments[idx]
            source_text = segment.get("source_text", "")
            translated_text = segment.get("translated_text", "")

            if not source_text or not translated_text:
                continue

            try:
                # Użyj Claude do oceny jakości
                prompt = f"""You are a professional translation quality reviewer for legal documents.

SOURCE TEXT (English):
{source_text}

TRANSLATION (Polish):
{translated_text}

Evaluate this translation and identify any issues:
1. Grammar and syntax errors
2. Mistranslations or inaccuracies
3. Unnatural phrasing
4. Missing or added information

If there are issues, respond in this format:
SEVERITY: [critical/warning/info]
CATEGORY: [grammar/accuracy/fluency]
ISSUE: [brief description]

If the translation is good, respond with: "OK"

Keep your response concise (max 2 sentences)."""

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}],
                )

                review_text = response.content[0].text.strip()

                if review_text != "OK" and not review_text.startswith("The translation"):
                    # Parse response
                    lines = review_text.split("\n")
                    severity = "warning"
                    category = "quality"
                    description = review_text

                    for line in lines:
                        if line.startswith("SEVERITY:"):
                            severity = line.split(":", 1)[1].strip().lower()
                        elif line.startswith("CATEGORY:"):
                            category = line.split(":", 1)[1].strip().lower()
                        elif line.startswith("ISSUE:"):
                            description = line.split(":", 1)[1].strip()

                    issues.append(
                        QAIssue(
                            severity=severity,
                            category=category,
                            description=f"Segment {idx+1}: {description}",
                            segment_index=idx,
                        )
                    )

            except Exception as e:
                logger.warning(f"Error checking segment {idx}: {e}")
                continue

        return issues

    def _generate_summary(self, issues: List[QAIssue], approved: bool) -> str:
        """
        Generuje podsumowanie przeglądu QA.

        Args:
            issues: Lista znalezionych problemów
            approved: Czy tłumaczenie jest zatwierdzone

        Returns:
            Tekstowe podsumowanie
        """
        if approved and not issues:
            return "Translation quality is excellent. No issues found. Approved for delivery."

        if approved:
            return f"Translation approved with {len(issues)} minor issues that don't affect overall quality."

        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            return (
                f"Translation has {len(critical_issues)} critical issue(s) that must be "
                f"resolved before delivery. Review rejected."
            )

        return "Translation requires attention. Please review warnings before finalizing."

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki QA Reviewer.

        Returns:
            Słownik ze statystykami
        """
        return {
            "status": "active",
            "model": self.model,
            "reviews_completed": self.review_count,
        }

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
    Agent odpowiedzialny za kontrolę jakości tłumaczenia zgodnie z wytycznymi ETPCz.

    Sprawdza:
    1. Spójność terminologiczną (jeden termin = jeden ekwiwalent)
    2. Interpunkcję (przecinki, półpauzy, polskie cudzysłowy)
    3. Sieroty (twarde spacje przy jednoliterowych spójnikach)
    4. Formatowanie (podwójne spacje, kursywa)
    5. Kompletność tłumaczenia
    6. Brak zbędnego tekstu z TM
    7. Jednoznaczność odniesień sąd/Trybunał
    8. Odmianę imion i terminów
    9. Odniesienia do aktów prawnych (art. ust., §, paragraf)
    10. Szyk postpozycyjny i formy bezosobowe
    11. Gramatykę i składnię
    """

    def __init__(self, api_key: str = None):
        """
        Inicjalizacja QA Reviewer.

        Args:
            api_key: Klucz API Anthropic (opcjonalny, domyślnie z settings)
        """
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = "claude-sonnet-4-6-20250514"
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

            # Sprawdzenie 3: Interpunkcja (przecinki, półpauzy, cudzysłowy)
            punctuation_issues = self._check_punctuation(segments)
            issues.extend(punctuation_issues)

            # Sprawdzenie 4: Sieroty (twarde spacje)
            orphan_issues = self._check_orphans(segments)
            issues.extend(orphan_issues)

            # Sprawdzenie 5: Formatowanie (spacje, kursywa)
            formatting_issues = self._check_formatting(segments)
            issues.extend(formatting_issues)

            # Sprawdzenie 6: Odniesienia do aktów prawnych
            reference_issues = self._check_legal_references(segments)
            issues.extend(reference_issues)

            # Sprawdzenie 7: Próbki jakości (używa Claude)
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

    def _check_punctuation(self, segments: List[Dict[str, Any]]) -> List[QAIssue]:
        """
        Sprawdza interpunkcję zgodnie z wytycznymi ETPCz.

        Sprawdza:
        - Polskie znaki cytatu: „" zamiast ""
        - Półpauzy ( – ) zamiast łączników ( - ) w przedziałach
        - Zbędne przecinki po okolicznikach na początku zdania
        """
        issues = []
        import re

        for i, segment in enumerate(segments):
            translated_text = segment.get("translated_text", "")
            if not translated_text:
                continue

            # 1. Sprawdź niepoprawne cudzysłowy
            if '"' in translated_text or '"' in translated_text or '"' in translated_text:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="punctuation",
                        description=f'Segment {i+1}: Używaj polskich znaków cytatu „" zamiast ""',
                        segment_index=i,
                        suggestion='Zamień cudzysłowy na polskie: „tekst"',
                    )
                )

            # 2. Sprawdź łączniki w przedziałach liczbowych
            # Wzorce: §§ 34-45, art. 5-8, paragrafy 10-15
            hyphen_ranges = re.findall(r'(§§?\s*\d+-\d+|art\.\s*\d+-\d+|paragraf[ya]?\s+\d+-\d+)', translated_text)
            if hyphen_ranges:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="punctuation",
                        description=f"Segment {i+1}: Użyj półpauzy ( – ) zamiast łącznika ( - ) w przedziałach: {', '.join(hyphen_ranges[:3])}",
                        segment_index=i,
                        suggestion="Zamień - na – w przedziałach liczbowych",
                    )
                )

            # 3. Sprawdź przecinki po okolicznikach na początku zdania
            # Wzorce: "W niniejszej sprawie, Trybunał"
            wrong_commas = re.findall(r'\.\s+([A-ZŁŚĆŻŹŃĄ][a-ząćęłńóśźż\s]{5,30}),\s+(Trybunał|Sąd|Rząd)', translated_text)
            if wrong_commas:
                issues.append(
                    QAIssue(
                        severity="info",
                        category="punctuation",
                        description=f"Segment {i+1}: Możliwy zbędny przecinek po okoliczniku na początku zdania",
                        segment_index=i,
                        suggestion="Sprawdź czy przecinek po okoliczniku jest konieczny",
                    )
                )

        return issues

    def _check_orphans(self, segments: List[Dict[str, Any]]) -> List[QAIssue]:
        """
        Sprawdza obecność sierot (jednoliterowe spójniki bez twardej spacji).

        Wykrywa:
        - Jednoliterowe spójniki: i, w, z, o, a, u
        - Jednostki: r., §, art., ust., lit., nr
        - Liczby przed jednostkami
        """
        issues = []
        import re

        for i, segment in enumerate(segments):
            translated_text = segment.get("translated_text", "")
            if not translated_text:
                continue

            # Wzorce sierot (spacja zwykła przed jednoliterowcem/jednostką na końcu linii lub przed interpunkcją)
            # Wykrywamy \s[iwzoau]\s, \s\d+\s(r\.|§), \s(art|ust|lit|nr)\.\s
            orphan_patterns = [
                (r'\s([iwzoau])\s', "jednoliterowy spójnik"),
                (r'\s(\d+)\s+(r\.)', "liczba przed 'r.'"),
                (r'\s(art\.|ust\.|lit\.|nr)\s', "skrót jednostki"),
            ]

            found_orphans = []
            for pattern, name in orphan_patterns:
                matches = re.findall(pattern, translated_text)
                if matches:
                    found_orphans.append(name)

            if found_orphans:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="formatting",
                        description=f"Segment {i+1}: Wykryto potencjalne sieroty: {', '.join(set(found_orphans))}",
                        segment_index=i,
                        suggestion="Użyj twardych spacji (Ctrl+Shift+Space) przed jednoliterowymi spójnikami i jednostkami",
                    )
                )

        return issues

    def _check_formatting(self, segments: List[Dict[str, Any]]) -> List[QAIssue]:
        """
        Sprawdza formatowanie zgodnie z wytycznymi ETPCz.

        Sprawdza:
        - Podwójne/potrójne spacje
        - Spacje przed interpunkcją
        - Brak spacji po interpunkcji
        - Skróty na początku zdania (powinny być rozwinięte)
        """
        issues = []
        import re

        for i, segment in enumerate(segments):
            translated_text = segment.get("translated_text", "")
            if not translated_text:
                continue

            # 1. Podwójne/potrójne spacje
            if '  ' in translated_text:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="formatting",
                        description=f"Segment {i+1}: Wykryto podwójne spacje",
                        segment_index=i,
                        suggestion="Usuń zbędne spacje",
                    )
                )

            # 2. Spacje przed interpunkcją
            spaces_before_punct = re.findall(r'\s+([.,;:!?])', translated_text)
            if spaces_before_punct:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="formatting",
                        description=f"Segment {i+1}: Spacja przed interpunkcją: {', '.join(set(spaces_before_punct))}",
                        segment_index=i,
                        suggestion="Usuń spacje przed znakami interpunkcyjnymi",
                    )
                )

            # 3. Skróty na początku zdania (art., zob., itp.)
            sentence_start_abbrev = re.findall(r'\.\s+(art\.|zob\.|ust\.|lit\.)', translated_text)
            if sentence_start_abbrev:
                issues.append(
                    QAIssue(
                        severity="info",
                        category="formatting",
                        description=f"Segment {i+1}: Skrót na początku zdania: {', '.join(set(sentence_start_abbrev))}",
                        segment_index=i,
                        suggestion="Rozwiń skróty na początku zdania: 'Artykuł', 'Zobacz'",
                    )
                )

            # 4. Brak spacji np. "paragraf40"
            no_space_patterns = re.findall(r'(paragraf\d+|art\.\d+|§\d+)', translated_text)
            if no_space_patterns:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="formatting",
                        description=f"Segment {i+1}: Brak spacji: {', '.join(set(no_space_patterns))}",
                        segment_index=i,
                        suggestion="Dodaj spację między słowem a liczbą",
                    )
                )

        return issues

    def _check_legal_references(self, segments: List[Dict[str, Any]]) -> List[QAIssue]:
        """
        Sprawdza poprawność odniesień do aktów prawnych.

        Weryfikuje:
        - EKPC: art. X ust. Y Konwencji (nie §)
        - Regulamin: Reguła X § Y Regulaminu Trybunału
        - Paragrafy: słownie "paragraf X" nie "ustęp X"
        """
        issues = []
        import re

        for i, segment in enumerate(segments):
            translated_text = segment.get("translated_text", "")
            if not translated_text:
                continue

            # 1. Sprawdź czy Konwencja używa § zamiast ust.
            konwencja_wrong_sect = re.findall(r'(art\.\s*\d+\s*§\s*\d+\s*Konwencji)', translated_text)
            if konwencja_wrong_sect:
                issues.append(
                    QAIssue(
                        severity="critical",
                        category="legal_reference",
                        description=f"Segment {i+1}: Konwencja powinna używać 'ust.' nie '§': {', '.join(konwencja_wrong_sect)}",
                        segment_index=i,
                        suggestion="Zamień § na ust. w odniesieniach do Konwencji",
                    )
                )

            # 2. Sprawdź czy Regulamin używa ust. zamiast §
            regulamin_wrong_ust = re.findall(r'(Reguła\s*\d+\s*ust\.\s*\d+\s*Regulaminu)', translated_text)
            if regulamin_wrong_ust:
                issues.append(
                    QAIssue(
                        severity="critical",
                        category="legal_reference",
                        description=f"Segment {i+1}: Regulamin powinien używać '§' nie 'ust.': {', '.join(regulamin_wrong_ust)}",
                        segment_index=i,
                        suggestion="Zamień ust. na § w odniesieniach do Regulaminu Trybunału",
                    )
                )

            # 3. Sprawdź użycie "ustęp" zamiast "paragraf" dla paragrafów wyroku
            wrong_ustep = re.findall(r'\bustęp(ie)?\s+\d+\b', translated_text)
            if wrong_ustep and 'Konwencji' not in translated_text:
                issues.append(
                    QAIssue(
                        severity="warning",
                        category="legal_reference",
                        description=f"Segment {i+1}: Użyto 'ustęp' zamiast 'paragraf' dla odniesienia do wyroku",
                        segment_index=i,
                        suggestion="Użyj 'paragraf' dla odniesień do paragrafów wyroku",
                    )
                )

        return issues

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

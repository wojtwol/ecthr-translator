# Specyfikacja agentów – ECTHR Translator

## Przegląd

| Agent | Rola | Technologia |
|-------|------|-------------|
| Orchestrator | Koordynacja workflow | Python (logika) |
| Format Handler | DOCX ↔ segmenty | python-docx |
| Structure Parser | Rozpoznawanie sekcji | Claude API |
| TM Manager | Pamięć tłumaczeniowa | TMX parser |
| Term Extractor | Ekstrakcja terminów | Claude API |
| Case Law Researcher | HUDOC + CURIA | HTTP scraping |
| Translator | Tłumaczenie | Claude API |
| Change Implementer | Reimplementacja zmian | Python (diff) |
| QA Reviewer | Kontrola jakości | Claude API |

---

## 1. ORCHESTRATOR

### Odpowiedzialność
Zarządza całym workflow tłumaczenia, koordynuje agentów, utrzymuje stan zadania.

### Implementacja
```python
class Orchestrator:
    def __init__(self, config: Config):
        self.format_handler = FormatHandler()
        self.structure_parser = StructureParser()
        self.tm_manager = TMManager(config.tm_path)
        self.term_extractor = TermExtractor()
        self.case_law_researcher = CaseLawResearcher()
        self.translator = Translator()
        self.change_implementer = ChangeImplementer()
        self.qa_reviewer = QAReviewer()

    async def process(self, document_id: str, source_path: str) -> TranslationResult:
        # Faza 1: Ekstrakcja i analiza
        segments = await self.format_handler.extract(source_path)
        parsed_segments = await self.structure_parser.parse(segments)

        # Faza 2: Terminologia
        tm_matches = await self.tm_manager.find_matches(parsed_segments)
        terms = await self.term_extractor.extract(parsed_segments, tm_matches)

        # Faza 3: Wzbogacenie z HUDOC/CURIA
        enriched_terms = await self.case_law_researcher.enrich(terms)

        # Faza 4: Tłumaczenie
        translated = await self.translator.translate(parsed_segments, enriched_terms)

        await self.save_draft(document_id, translated, enriched_terms)
        return {"status": "awaiting_validation", "terms": enriched_terms}

    async def finalize(self, document_id: str, validated_terms: List[Term]) -> TranslationResult:
        draft = await self.load_draft(document_id)
        implemented = await self.change_implementer.implement(draft, validated_terms)
        reviewed = await self.qa_reviewer.review(implemented)
        output_path = await self.format_handler.reconstruct(reviewed)
        await self.tm_manager.update(validated_terms)
        return {"status": "completed", "translated_path": output_path}
```

---

## 2. FORMAT HANDLER

### Odpowiedzialność
Parsuje DOCX na segmenty tekstowe z zachowaniem metadanych formatowania. Rekonstruuje DOCX z przetłumaczonych segmentów.

### Implementacja
```python
from docx import Document
from docx.shared import Pt, Inches

class FormatHandler:
    def extract(self, source_path: str) -> Dict:
        doc = Document(source_path)
        segments = []

        for i, para in enumerate(doc.paragraphs):
            segment = {
                "index": i,
                "text": para.text,
                "format": self._extract_format(para),
                "parent_type": "paragraph",
            }
            segments.append(segment)

        # Obsługa tabel
        for table in doc.tables:
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell in enumerate(row.cells):
                    for para in cell.paragraphs:
                        segment = {
                            "index": len(segments),
                            "text": para.text,
                            "format": self._extract_format(para),
                            "parent_type": "table_cell",
                            "table_position": {"row": row_idx, "col": col_idx}
                        }
                        segments.append(segment)

        return {"segments": segments, "document_metadata": self._extract_metadata(doc)}

    def reconstruct(self, translated_segments: List[Dict], metadata: Dict, output_path: str) -> str:
        doc = Document()
        self._apply_styles(doc, metadata["styles"])

        for segment in translated_segments:
            if segment["parent_type"] == "paragraph":
                para = doc.add_paragraph()
                self._apply_format(para, segment["format"])
                para.text = segment["text"]

        doc.save(output_path)
        return output_path
```

---

## 3. STRUCTURE PARSER

### Odpowiedzialność
Rozpoznaje strukturę orzeczenia ETPCz i klasyfikuje segmenty według sekcji.

### Struktura orzeczenia ETPCz
```
1. PROCEDURE - numer sprawy, data, skład sędziowski
2. THE FACTS
   - I. THE CIRCUMSTANCES OF THE CASE
   - II. RELEVANT DOMESTIC LAW AND PRACTICE
3. THE LAW
   - ALLEGED VIOLATION OF ARTICLE X
   - Dopuszczalność, Meritum
4. OPERATIVE PROVISIONS - sentencja
```

### Prompt dla Claude
```python
STRUCTURE_PARSER_PROMPT = """
Jesteś ekspertem w analizie orzeczeń Europejskiego Trybunału Praw Człowieka (ETPCz).

Przeanalizuj poniższy segment tekstu i określ, do której sekcji orzeczenia należy:
- PROCEDURE: informacje proceduralne, skład sędziowski, daty
- FACTS: stan faktyczny sprawy, okoliczności, prawo krajowe
- LAW: ocena prawna, analiza zarzutów, dopuszczalność, meritum
- OPERATIVE: sentencja, rozstrzygnięcie, koszty

Segment:
{segment_text}

Kontekst (poprzednie segmenty):
{context}

Odpowiedz w formacie JSON:
{
    "section_type": "PROCEDURE" | "FACTS" | "LAW" | "OPERATIVE",
    "confidence": 0.0-1.0,
    "subsection": "opcjonalnie, np. 'CIRCUMSTANCES OF THE CASE'",
    "reasoning": "krótkie uzasadnienie klasyfikacji"
}
"""
```

---

## 4. TM MANAGER

### Odpowiedzialność
Zarządza pamięcią tłumaczeniową (TMX). Znajduje dopasowania exact i fuzzy.

### Implementacja
```python
from rapidfuzz import fuzz

class TMManager:
    def load(self, tm_path: str) -> None:
        """Ładuje plik TMX do pamięci."""

    def find_exact(self, source_text: str) -> Optional[TMEntry]:
        """Szuka dokładnego dopasowania."""

    def find_fuzzy(self, source_text: str, threshold: float = 0.75) -> List[TMEntry]:
        """Szuka podobnych segmentów."""
        return [entry for entry in self.entries
                if fuzz.ratio(source_text.lower(), entry.source.lower()) / 100.0 >= threshold]

    def add_entry(self, source: str, target: str, metadata: Dict) -> None:
        """Dodaje nowy wpis do TM."""

    def save(self) -> None:
        """Zapisuje TM do pliku."""
```

---

## 5. TERM EXTRACTOR

### Prompt dla Claude
```python
TERM_EXTRACTOR_PROMPT = """
Jesteś ekspertem w terminologii prawniczej ETPCz.

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

Odpowiedz w formacie JSON:
{
    "terms": [
        {
            "source_term": "margin of appreciation",
            "proposed_translation": "margines oceny",
            "context": "zdanie, w którym termin występuje",
            "term_type": "ecthr_specific" | "procedural" | "convention" | "latin",
            "confidence": 0.0-1.0
        }
    ]
}
"""
```

---

## 6. CASE LAW RESEARCHER

### HUDOC Client
```python
class HUDOCClient:
    BASE_URL = "https://hudoc.echr.coe.int"

    async def search_by_term(self, term: str, language: str = "ENG") -> List[Dict]:
        """Szuka orzeczeń zawierających dany termin."""

    async def find_term_in_translations(self, term_en: str) -> List[Dict]:
        """Szuka terminu w angielskich orzeczeniach i sprawdza tłumaczenie PL."""
        results = []
        cases = await self.search_by_term(term_en)

        for case in cases[:5]:
            en_text = await self.get_case(case["id"])
            pl_text = await self.get_translation(case["id"], "POL")

            if pl_text:
                pl_equivalent = self._align_terms(en_text, pl_text, term_en)
                if pl_equivalent:
                    results.append({
                        "term_en": term_en,
                        "term_pl": pl_equivalent,
                        "case_name": case["title"],
                        "source": "hudoc"
                    })
        return results
```

### CURIA Client
```python
class CURIAClient:
    BASE_URL = "https://curia.europa.eu"

    async def search_term(self, term: str) -> List[Dict]:
        """Szuka terminu w orzecznictwie TSUE."""

    async def get_multilingual_term(self, term_en: str) -> Dict:
        """Znajduje oficjalne tłumaczenia terminu."""
```

---

## 7. TRANSLATOR

### Prompt dla Claude
```python
TRANSLATOR_PROMPT = """
Jesteś profesjonalnym tłumaczem prawniczym specjalizującym się w orzeczeniach ETPCz.

Przetłumacz poniższy segment na język polski, zachowując:
- Styl i rejestr orzeczeń sądowych
- Spójność terminologiczną (użyj TYLKO podanych ekwiwalentów)
- Strukturę zdań typową dla polskiego języka prawniczego

Segment do tłumaczenia:
{source_text}

Typ sekcji: {section_type}

OBOWIĄZKOWA TERMINOLOGIA (użyj dokładnie tych ekwiwalentów):
| Termin angielski | Polski ekwiwalent |
{terminology_table}

Kontekst (poprzednie przetłumaczone segmenty):
{context}

Przetłumacz segment. Nie dodawaj żadnych komentarzy ani wyjaśnień.
"""
```

---

## 8. CHANGE IMPLEMENTER

### Implementacja
```python
class ChangeImplementer:
    def implement(self, segments: List[Segment], original_terms: List[Term], validated_terms: List[Term]) -> List[Segment]:
        changes = self._diff_terms(original_terms, validated_terms)

        for segment in segments:
            for change in changes:
                if change.type == "EDITED":
                    segment.target_text = segment.target_text.replace(
                        change.old_term, change.new_term
                    )
                elif change.type == "REJECTED":
                    segment.target_text = segment.target_text.replace(
                        change.old_term, f"[DO WERYFIKACJI: {change.source_term}]"
                    )
        return segments
```

---

## 9. QA REVIEWER

### Prompt dla Claude
```python
QA_REVIEWER_PROMPT = """
Jesteś kontrolerem jakości tłumaczeń prawniczych ETPCz.

Sprawdź tłumaczenie pod kątem:
1. SPÓJNOŚĆ TERMINOLOGICZNA - czy wszystkie wystąpienia terminu są przetłumaczone tak samo?
2. KOMPLETNOŚĆ - czy wszystkie elementy źródła są przetłumaczone?
3. POPRAWNOŚĆ JĘZYKOWA - czy tłumaczenie jest gramatycznie poprawne?
4. REFERENCJE - czy numery artykułów i sygnatury spraw są zachowane?

Tekst źródłowy:
{source_text}

Tłumaczenie:
{target_text}

Zatwierdzona terminologia:
{terminology}

Odpowiedz w formacie JSON:
{
    "passed": true | false,
    "issues": [
        {
            "type": "terminology" | "completeness" | "grammar" | "reference",
            "severity": "error" | "warning",
            "location": "fragment tekstu",
            "description": "opis problemu",
            "suggestion": "sugerowana poprawka"
        }
    ],
    "score": 0.0-1.0
}
"""
```

# Architektura techniczna – ECTHR Translator

## Diagram przepływu danych

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              UŻYTKOWNIK                                     │
│                                  │                                          │
│                          Upload DOCX                                        │
│                                  ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         REACT FRONTEND                                │  │
│  │                                                                       │  │
│  │   FileUpload → TranslationPage → GlossaryPanel → TranslationPreview  │  │
│  │                         │              ▲                              │  │
│  │                         │              │ WebSocket (progress)         │  │
│  │                         ▼              │                              │  │
│  └─────────────────────────┼──────────────┼──────────────────────────────┘  │
│                            │ REST API     │                                 │
│                            ▼              │                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        FASTAPI BACKEND                              │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │  /documents │  │  /glossary  │  │ /translation│                 │   │
│  │  │             │  │             │  │             │                 │   │
│  │  │ POST upload │  │ GET terms   │  │ POST start  │                 │   │
│  │  │ GET download│  │ PUT approve │  │ GET status  │                 │   │
│  │  │ GET status  │  │ PUT edit    │  │ WS progress │                 │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│  │         │                │                │                         │   │
│  │         └────────────────┼────────────────┘                         │   │
│  │                          ▼                                          │   │
│  │  ┌───────────────────────────────────────────────────────────────┐ │   │
│  │  │                     ORCHESTRATOR                              │ │   │
│  │  │                                                               │ │   │
│  │  │   Zarządza workflow, kolejnością agentów, stanem zadania     │ │   │
│  │  └───────────────────────┬───────────────────────────────────────┘ │   │
│  │                              │                                     │   │
│  │         ┌────────────────────┼────────────────────┐               │   │
│  │         ▼                    ▼                    ▼               │   │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌─────────────┐           │   │
│  │  │   FORMAT    │  │   STRUCTURE     │  │     TM      │           │   │
│  │  │   HANDLER   │  │   PARSER        │  │   MANAGER   │           │   │
│  │  │             │  │                 │  │             │           │   │
│  │  │ python-docx │  │ Claude API      │  │ TMX parser  │           │   │
│  │  └─────────────┘  └─────────────────┘  └─────────────┘           │   │
│  │         │                    │                    │               │   │
│  │         └────────────────────┼────────────────────┘               │   │
│  │                              ▼                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────┐│   │
│  │  │                    TERM EXTRACTOR                             ││   │
│  │  │                                                               ││   │
│  │  │   Wykrywa terminy prawnicze, proponuje ekwiwalenty           ││   │
│  │  │   Źródła: TM → HUDOC → CURIA → Claude (propozycja)           ││   │
│  │  └───────────────────────────┬───────────────────────────────────┘│   │
│  │                              │                                    │   │
│  │         ┌────────────────────┴────────────────────┐              │   │
│  │         ▼                                         ▼              │   │
│  │  ┌─────────────────┐                   ┌─────────────────┐       │   │
│  │  │  HUDOC CLIENT   │                   │  CURIA CLIENT   │       │   │
│  │  │                 │                   │                 │       │   │
│  │  │ hudoc.echr.coe  │                   │ curia.europa.eu │       │   │
│  │  └─────────────────┘                   └─────────────────┘       │   │
│  │                              │                                    │   │
│  │                              ▼                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────┐│   │
│  │  │                      TRANSLATOR                               ││   │
│  │  │                                                               ││   │
│  │  │   Tłumaczy segment po segmencie z wykorzystaniem:            ││   │
│  │  │   - Zatwierdzonej terminologii                               ││   │
│  │  │   - Kontekstu sekcji (Facts vs Law vs Operative)             ││   │
│  │  │   - Stylu orzeczeń ETPCz                                     ││   │
│  │  └───────────────────────────────────────────────────────────────┘│   │
│  │                              │                                    │   │
│  │                              ▼                                    │   │
│  │                    ┌─────────────────┐                           │   │
│  │                    │  DRAFT OUTPUT   │                           │   │
│  │                    │                 │                           │   │
│  │                    │ + Glosariusz    │ ──→ UI do walidacji       │   │
│  │                    └─────────────────┘                           │   │
│  │                              │                                    │   │
│  │                      [Walidacja użytkownika]                     │   │
│  │                              │                                    │   │
│  │                              ▼                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────┐│   │
│  │  │                  CHANGE IMPLEMENTER                           ││   │
│  │  │                                                               ││   │
│  │  │   Porównuje glosariusz przed/po walidacji                    ││   │
│  │  │   Podmienia terminy w całym dokumencie                       ││   │
│  │  └───────────────────────────┬───────────────────────────────────┘│   │
│  │                              │                                    │   │
│  │                              ▼                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────┐│   │
│  │  │                     QA REVIEWER                               ││   │
│  │  │                                                               ││   │
│  │  │   Sprawdza: spójność terminologii, kompletność, format       ││   │
│  │  └───────────────────────────┬───────────────────────────────────┘│   │
│  │                              │                                    │   │
│  │                              ▼                                    │   │
│  │                    ┌─────────────────┐                           │   │
│  │                    │  FINAL OUTPUT   │                           │   │
│  │                    │                 │                           │   │
│  │                    │ DOCX + TM update│                           │   │
│  │                    └─────────────────┘                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Model danych

### Tabele SQLite/PostgreSQL

```sql
-- Dokumenty źródłowe i przetłumaczone
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    translated_path TEXT,
    status TEXT DEFAULT 'uploaded',  -- uploaded, analyzing, translating, validating, completed, error
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Segmenty dokumentu
CREATE TABLE segments (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    index INTEGER NOT NULL,
    source_text TEXT NOT NULL,
    target_text TEXT,
    section_type TEXT,  -- procedure, facts, law, operative, other
    format_metadata JSON,  -- style, bold, italic, etc.
    status TEXT DEFAULT 'pending',  -- pending, translated, reviewed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Terminy w glosariuszu
CREATE TABLE terms (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    source_term TEXT NOT NULL,
    target_term TEXT,
    source_type TEXT,  -- tm_exact, tm_fuzzy, hudoc, curia, proposed
    confidence REAL,  -- 0.0 - 1.0
    status TEXT DEFAULT 'pending',  -- pending, approved, edited, rejected
    original_proposal TEXT,  -- zachowuje oryginalną propozycję przed edycją
    references JSON,  -- linki do źródeł (HUDOC, CURIA, TM entries)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historia zmian terminów (audit trail)
CREATE TABLE term_history (
    id TEXT PRIMARY KEY,
    term_id TEXT REFERENCES terms(id),
    action TEXT,  -- created, edited, approved, rejected
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zadania tłumaczeniowe
CREATE TABLE translation_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    phase TEXT,  -- analysis, translation, validation, implementation, completed
    progress REAL DEFAULT 0.0,
    current_step TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Pydantic Models (Backend)

```python
# models/document.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    TRANSLATING = "translating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"

class Document(BaseModel):
    id: str
    filename: str
    original_path: str
    translated_path: Optional[str]
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

# models/term.py
class TermSource(str, Enum):
    TM_EXACT = "tm_exact"
    TM_FUZZY = "tm_fuzzy"
    HUDOC = "hudoc"
    CURIA = "curia"
    PROPOSED = "proposed"

class TermStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"

class Term(BaseModel):
    id: str
    document_id: str
    source_term: str
    target_term: Optional[str]
    source_type: TermSource
    confidence: float
    status: TermStatus
    original_proposal: Optional[str]
    references: Optional[List[dict]]

class TermUpdate(BaseModel):
    target_term: str
    status: TermStatus

# models/segment.py
class SectionType(str, Enum):
    PROCEDURE = "procedure"
    FACTS = "facts"
    LAW = "law"
    OPERATIVE = "operative"
    OTHER = "other"

class Segment(BaseModel):
    id: str
    document_id: str
    index: int
    source_text: str
    target_text: Optional[str]
    section_type: SectionType
    format_metadata: Optional[dict]
```

## Format pamięci tłumaczeniowej (TMX)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4">
  <header
    creationtool="ECTHR-Translator"
    creationtoolversion="1.0"
    segtype="sentence"
    o-tmf="ECTHR"
    adminlang="en"
    srclang="en"
    datatype="plaintext">
  </header>
  <body>
    <tu>
      <tuv xml:lang="en">
        <seg>margin of appreciation</seg>
      </tuv>
      <tuv xml:lang="pl">
        <seg>margines oceny</seg>
      </tuv>
      <prop type="source">hudoc</prop>
      <prop type="case">Handyside v. UK</prop>
      <prop type="date">2024-01-15</prop>
    </tu>
  </body>
</tmx>
```

## Komunikacja Frontend ↔ Backend

### REST API

```
POST   /api/documents/upload          # Upload DOCX
GET    /api/documents/{id}            # Status dokumentu
GET    /api/documents/{id}/download   # Pobierz przetłumaczony DOCX

POST   /api/translation/{doc_id}/start    # Uruchom tłumaczenie
GET    /api/translation/{doc_id}/status   # Status zadania

GET    /api/glossary/{doc_id}             # Lista terminów
PUT    /api/glossary/{doc_id}/{term_id}   # Aktualizuj termin
POST   /api/glossary/{doc_id}/approve-all # Zatwierdź wszystkie

GET    /api/preview/{doc_id}              # Podgląd tłumaczenia z segmentami
```

### WebSocket

```
WS /ws/translation/{doc_id}

# Server → Client messages:
{
  "type": "progress",
  "phase": "analysis",
  "progress": 0.45,
  "current_step": "Extracting terms..."
}

{
  "type": "term_found",
  "term": {
    "id": "term_123",
    "source_term": "just satisfaction",
    "target_term": "słuszne zadośćuczynienie",
    "source_type": "hudoc",
    "confidence": 1.0
  }
}

{
  "type": "phase_complete",
  "phase": "translation",
  "next_phase": "validation"
}

{
  "type": "error",
  "message": "HUDOC unavailable, continuing with TM only"
}
```

## Hierarchia źródeł terminologicznych

```python
TERM_SOURCE_PRIORITY = [
    ("tm_exact", 1.0),      # TM exact match – najwyższy priorytet
    ("hudoc", 0.95),        # HUDOC oficjalne tłumaczenie
    ("curia", 0.90),        # CURIA terminologia UE
    ("tm_fuzzy", 0.75),     # TM fuzzy match (>75% similarity)
    ("proposed", 0.60),     # Propozycja Claude
]
```

## Obsługa błędów i retry

```python
HUDOC_RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,
    "timeout": 30,
}

CURIA_RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,
    "timeout": 30,
}

CLAUDE_RETRY_CONFIG = {
    "max_attempts": 5,
    "backoff_factor": 1.5,
    "timeout": 120,
}
```

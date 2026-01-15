# ECTHR Translator – Instrukcja dla Claude Code

## Cel projektu

System do tłumaczenia orzeczeń Europejskiego Trybunału Praw Człowieka (ETPCz) z języka angielskiego na polski, z jednoczesną ekstrakcją i zarządzaniem terminologią prawniczą.

## Kontekst biznesowy

- **Użytkownik**: IURIDICO Legal & Financial Translations (tłumaczenia prawnicze)
- **Dokumenty**: Orzeczenia ETPCz (przewidywalna struktura: Procedure, Facts, The Law, Operative provisions)
- **Kierunek**: EN → PL
- **Istniejące zasoby**: Obszerna pamięć tłumaczeniowa (TM) z wcześniejszych projektów

## Kluczowe funkcjonalności

1. **Tłumaczenie z zachowaniem formatu** – DOCX wejściowy → DOCX wyjściowy z identycznym formatowaniem
2. **Ekstrakcja terminologii** – automatyczne wykrywanie terminów prawniczych
3. **Weryfikacja w źródłach** – przeszukiwanie HUDOC i CURIA dla oficjalnych ekwiwalentów
4. **Human-in-the-loop** – webowy interfejs do zatwierdzania terminów jeden po drugim
5. **Automatyczny feedback do TM** – zatwierdzone terminy trafiają do pamięci tłumaczeniowej

## Stack technologiczny

```
Frontend:   React 18 + Tailwind CSS + React Query
Backend:    FastAPI (Python 3.11+)
Baza:       SQLite (lokalnie) → PostgreSQL (produkcja)
Format TM:  TMX (Translation Memory eXchange)
Kontener:   Docker + Docker Compose
```

## Architektura agentów

System składa się z wyspecjalizowanych agentów koordynowanych przez Orchestrator:

```
ORCHESTRATOR
    │
    ├── FORMAT HANDLER      # DOCX ↔ segmenty tekstowe
    ├── STRUCTURE PARSER    # Rozpoznaje sekcje orzeczenia ETPCz
    ├── TM MANAGER          # Pamięć tłumaczeniowa (exact + fuzzy match)
    ├── CASE LAW RESEARCHER # Przeszukuje HUDOC i CURIA
    ├── TERM EXTRACTOR      # Wyciąga nowe terminy
    ├── TRANSLATOR          # Tłumaczy z wykorzystaniem terminologii
    ├── CHANGE IMPLEMENTER  # Wdraża poprawki po walidacji człowieka
    └── QA REVIEWER         # Kontrola spójności
```

## Workflow

```
FAZA 1: ANALIZA
───────────────
Upload DOCX → Format Handler (ekstrakcja) → Structure Parser
                                                    ↓
TM Manager (szuka dopasowań) ←──── Term Extractor (wykrywa terminy)
                                                    ↓
                              Case Law Researcher (HUDOC/CURIA)

FAZA 2: TŁUMACZENIE WSTĘPNE
───────────────────────────
Translator generuje draft z glosariuszem

FAZA 3: WALIDACJA (UI)
──────────────────────
Użytkownik przegląda terminy jeden po drugim:
- ✓ Zatwierdza
- ✎ Edytuje
- ✗ Odrzuca (flaga do ręcznego tłumaczenia)

FAZA 4: REIMPLEMENTACJA
───────────────────────
Change Implementer → QA Reviewer → Format Handler (rekonstrukcja DOCX)
                                            ↓
                                    Automatyczny update TM
```

## Struktura projektu

```
ecthr-translator/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Konfiguracja (env vars)
│   ├── routers/
│   │   ├── documents.py        # Upload, download, status
│   │   ├── glossary.py         # CRUD terminów
│   │   └── translation.py      # Uruchomienie tłumaczenia
│   ├── services/
│   │   ├── tm_manager.py       # Pamięć tłumaczeniowa (TMX)
│   │   ├── hudoc_client.py     # Scraper HUDOC
│   │   └── curia_client.py     # Scraper CURIA
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── format_handler.py
│   │   ├── structure_parser.py
│   │   ├── term_extractor.py
│   │   ├── case_law_researcher.py
│   │   ├── translator.py
│   │   ├── change_implementer.py
│   │   └── qa_reviewer.py
│   ├── models/
│   │   ├── document.py         # SQLAlchemy models
│   │   ├── term.py
│   │   └── translation_job.py
│   └── db/
│       └── database.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.jsx
│   │   │   ├── GlossaryPanel.jsx
│   │   │   ├── TermEditor.jsx
│   │   │   ├── TranslationPreview.jsx
│   │   │   └── ProgressBar.jsx
│   │   ├── pages/
│   │   │   ├── HomePage.jsx
│   │   │   └── TranslationPage.jsx
│   │   ├── hooks/
│   │   │   └── useTranslation.js
│   │   ├── api/
│   │   │   └── client.js
│   │   └── App.jsx
│   ├── package.json
│   └── tailwind.config.js
├── data/
│   ├── tm/                     # Pamięci tłumaczeniowe (TMX)
│   ├── uploads/                # Pliki źródłowe
│   └── outputs/                # Przetłumaczone dokumenty
├── docs/                       # Dokumentacja projektu
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── .env.example
└── README.md
```

## Kolejność implementacji

### Sprint 1: Fundament
1. Inicjalizacja projektu (Docker, struktura katalogów)
2. Backend: FastAPI skeleton + endpointy upload/download
3. Format Handler: parsowanie DOCX → segmenty → DOCX
4. Frontend: FileUpload + podstawowy layout

### Sprint 2: Pipeline tłumaczenia
5. Structure Parser: rozpoznawanie sekcji ETPCz
6. TM Manager: ładowanie TMX, exact/fuzzy match
7. Term Extractor: ekstrakcja terminów z Claude
8. Translator: tłumaczenie segmentów

### Sprint 3: Źródła zewnętrzne
9. HUDOC Client: scraping/API
10. CURIA Client: scraping/API
11. Case Law Researcher: integracja źródeł

### Sprint 4: UI walidacji
12. GlossaryPanel: lista terminów
13. TermEditor: modal edycji
14. TranslationPreview: podgląd z podświetlaniem
15. WebSocket: live progress

### Sprint 5: Finalizacja
16. Change Implementer: reimplementacja po walidacji
17. QA Reviewer: kontrola spójności
18. Automatyczny update TM
19. Testy end-to-end

## Dokumentacja szczegółowa

Szczegółowa dokumentacja znajduje się w katalogu `docs/`:
- `ARCHITECTURE.md` – diagramy, model danych, przepływ
- `AGENTS.md` – specyfikacja każdego agenta z promptami
- `API.md` – dokumentacja REST API i WebSocket
- `UI_SPEC.md` – wireframes i komponenty React
- `SETUP.md` – instrukcja instalacji

## Konfiguracja (.env)

```env
ANTHROPIC_API_KEY=sk-ant-...
TM_PATH=./data/tm
UPLOAD_PATH=./data/uploads
OUTPUT_PATH=./data/outputs
DATABASE_URL=sqlite:///./data/ecthr.db
LOG_LEVEL=INFO
```

## Uruchomienie

```bash
docker-compose up --build
```

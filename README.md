# ECTHR Translator

System do tłumaczenia orzeczeń Europejskiego Trybunału Praw Człowieka (ETPCz) z języka angielskiego na polski, z wykorzystaniem AI do ekstrakcji i zarządzania terminologią prawniczą.

## Funkcjonalności

- **Tłumaczenie z zachowaniem formatu** – DOCX wejściowy → DOCX wyjściowy z identycznym formatowaniem
- **Inteligentna ekstrakcja terminologii** – automatyczne wykrywanie terminów prawniczych
- **Weryfikacja w oficjalnych źródłach** – przeszukiwanie HUDOC i CURIA
- **Human-in-the-loop** – interfejs webowy do zatwierdzania terminów
- **Automatyczny update TM** – zatwierdzone terminy trafiają do pamięci tłumaczeniowej

## Stack technologiczny

- **Frontend**: React 18 + Tailwind CSS + React Query
- **Backend**: FastAPI (Python 3.11+)
- **AI**: Anthropic Claude API
- **Baza**: SQLite (lokalnie) → PostgreSQL (produkcja)
- **Format TM**: TMX (Translation Memory eXchange)
- **Kontener**: Docker + Docker Compose

## Szybki start

```bash
# Klonowanie repo
git clone https://github.com/[user]/ecthr-translator.git
cd ecthr-translator

# Konfiguracja
cp .env.example .env
# Edytuj .env i dodaj ANTHROPIC_API_KEY

# Uruchomienie
docker-compose up --build
```

Dostęp:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Dokumentacja

- **[CLAUDE.md](CLAUDE.md)** – Pełna instrukcja dla Claude Code
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** – Architektura techniczna, model danych
- **[docs/AGENTS.md](docs/AGENTS.md)** – Specyfikacja agentów AI
- **[docs/API.md](docs/API.md)** – Dokumentacja REST API i WebSocket
- **[docs/UI_SPEC.md](docs/UI_SPEC.md)** – Specyfikacja interfejsu użytkownika
- **[docs/SETUP.md](docs/SETUP.md)** – Szczegółowa instrukcja instalacji

## Workflow

1. **Upload** – Użytkownik przesyła plik DOCX z orzeczeniem ETPCz
2. **Analiza** – System parsuje dokument i rozpoznaje strukturę
3. **Ekstrakcja terminów** – AI identyfikuje terminy prawnicze
4. **Wzbogacenie** – Wyszukiwanie ekwiwalentów w HUDOC/CURIA i pamięci tłumaczeniowej
5. **Tłumaczenie wstępne** – AI tłumaczy dokument z użyciem znalezionej terminologii
6. **Walidacja** – Użytkownik przegląda i zatwierdza terminy przez interfejs webowy
7. **Finalizacja** – System reimplementuje zmiany i generuje przetłumaczony DOCX
8. **Update TM** – Zatwierdzone terminy trafiają do pamięci tłumaczeniowej

## Struktura projektu

```
ecthr-translator/
├── backend/          # FastAPI backend
├── frontend/         # React frontend
├── data/
│   ├── tm/          # Translation Memory (TMX)
│   ├── uploads/     # Pliki źródłowe
│   └── outputs/     # Przetłumaczone dokumenty
├── docs/            # Dokumentacja
└── docker-compose.yml
```

## Rozwój

Projekt jest podzielony na 5 sprintów:

1. **Sprint 1**: Fundament – FastAPI, Format Handler, podstawowy React UI
2. **Sprint 2**: Pipeline tłumaczenia – Structure Parser, TM Manager, Term Extractor, Translator
3. **Sprint 3**: Źródła zewnętrzne – HUDOC Client, CURIA Client
4. **Sprint 4**: UI walidacji – GlossaryPanel, TermEditor, WebSocket
5. **Sprint 5**: Finalizacja – Change Implementer, QA Reviewer, testy e2e

## Licencja

MIT

## Kontakt

IURIDICO Legal & Financial Translations

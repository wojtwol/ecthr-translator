# ECTHR Translator — Inteligentny system tłumaczenia orzeczeń Europejskiego Trybunału Praw Człowieka

## Streszczenie

ECTHR Translator to wieloagentowy system AI do profesjonalnego tłumaczenia wyroków Europejskiego Trybunału Praw Człowieka (ETPCz) z języka angielskiego na polski. Łączy duże modele językowe (Claude firmy Anthropic) z bazami orzecznictwa (HUDOC, CURIA), terminologii prawnej UE (IATE) oraz pamięcią tłumaczeniową (TM). System implementuje workflow z walidacją przez człowieka (human-in-the-loop), pozwalając tłumaczom na kontrolę nad terminologią przy jednoczesnym wykorzystaniu automatyzacji AI.

---

## 1. Kontekst i motywacja

### Problem

Tłumaczenie orzeczeń ETPCz wymaga:
- **Precyzyjnej terminologii prawnej** — „margin of appreciation" to „margines oceny" (nie „uznania"), „alleged violation" to „zarzucane naruszenie" (nie „domniemane")
- **Znajomości orzecznictwa** — odniesienia do wcześniejszych wyroków muszą być spójne z oficjalnymi tłumaczeniami
- **Zachowania formatowania** — dokumenty DOCX z numeracją paragrafów, tabelami, przypisami
- **Zgodności z wytycznymi ETPCz** — specyficzne zasady cytowania, jednostki redakcyjne (ust./§), cudzysłowy polskie

Tradycyjne narzędzia CAT (Computer-Assisted Translation) nie rozumieją kontekstu prawnego i nie potrafią automatycznie wyszukiwać orzecznictwa.

### Rozwiązanie

System wieloagentowy, gdzie wyspecjalizowane moduły AI współpracują z bazami wiedzy prawnej:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ECTHR Translator                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   HUDOC      │  │    CURIA     │  │    IATE      │              │
│  │  (ETPCz)     │  │   (TSUE)     │  │ (term. UE)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼───────┐                                 │
│                    │ Case Law     │                                 │
│                    │ Researcher   │                                 │
│                    └──────┬───────┘                                 │
│                           │                                         │
│  ┌────────────┐    ┌──────▼───────┐    ┌────────────┐              │
│  │  Term      │◄───┤ Orchestrator ├───►│ Translator │              │
│  │ Extractor  │    │   (Claude)   │    │  (Claude)  │              │
│  └────────────┘    └──────┬───────┘    └────────────┘              │
│                           │                                         │
│                    ┌──────▼───────┐                                 │
│                    │     TM       │◄── Pamięć Tłumaczeniowa        │
│                    │   Manager    │    (TMX/TBX)                   │
│                    └──────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architektura systemu

### 2.1 Stack technologiczny

| Warstwa | Technologie |
|---------|------------|
| Frontend | React 18, Vite, TailwindCSS, React Query, WebSocket |
| Backend | FastAPI, SQLAlchemy, Uvicorn, WebSockets |
| AI | Anthropic Claude API (claude-sonnet-4-5-20250929) |
| Bazy danych | SQLite (dev) / PostgreSQL (prod) |
| Źródła wiedzy | HUDOC API, CURIA, IATE, TMX/TBX |
| Deployment | Render.com, Docker, Vercel |

### 2.2 System agentów

System wykorzystuje **7 wyspecjalizowanych agentów**, każdy z dedykowanym promptem:

#### 1. **Orchestrator** — koordynator pipeline'u
- Zarządza 5-fazowym workflow tłumaczenia
- Obsługuje batching (10 segmentów na partię)
- Koordynuje komunikację między agentami
- Obsługuje finalizację i eksport

#### 2. **Structure Parser** — analiza struktury dokumentu
- Klasyfikuje segmenty: PROCEDURE, FACTS, LAW, OPERATIVE, OTHER
- Rozpoznaje nagłówki, numery paragrafów, cytaty
- Dostarcza kontekst dla tłumaczenia

#### 3. **Term Extractor** — ekstrakcja terminologii
- Identyfikuje terminy prawne w tekście źródłowym
- Priorytetyzacja: EKPC > ETPCz > proceduralne > łacińskie > nazwy instytucji
- Zachowuje kontekst użycia terminu
- Prompt: 80+ reguł ekstrakcji

#### 4. **Case Law Researcher** — badanie orzecznictwa
- Wyszukuje w HUDOC (ETPCz), CURIA (TSUE), IATE (UE)
- Hierarchia źródeł: TM (1.0) > HUDOC (0.95) > CURIA (0.90) > IATE (0.85) > propozycja AI (0.70)
- Zatrzymuje się po znalezieniu dopasowania (early stopping)
- Dostarcza odniesienia do konkretnych spraw

#### 5. **Translator** — tłumaczenie segmentów
- Tłumaczy EN→PL z użyciem Claude
- Prompt: **86 reguł** specyficznych dla ETPCz:
  - Terminologia (margines oceny, skarżący, Kanclerz Sekcji)
  - Jednostki redakcyjne (art. X ust. Y Konwencji vs Reguła X § Y Regulaminu)
  - Cytowanie (skarga nr 12345/19, §§ 34–45)
  - Gramatyka polska (szyk postpozycyjny, formy bezosobowe)
  - Interpunkcja (cudzysłowy „...", półpauzy w przedziałach)
- Temperatura: 0.3 (niska dla spójności)

#### 6. **Change Implementer** — implementacja zmian terminologicznych
- Re-tłumaczy segmenty z zatwierdzonymi terminami
- Stosuje odmianę przez przypadki
- Zachowuje spójność w całym dokumencie

#### 7. **QA Reviewer** — kontrola jakości
- 11 automatycznych kontroli:
  - Kompletność (brak pustych tłumaczeń)
  - Spójność terminologiczna
  - Cudzysłowy polskie
  - Półpauzy w przedziałach
  - Sieroty (twarde spacje)
  - Odniesienia prawne (ust. vs §)
- Wyniki informacyjne — nie blokują pobierania

### 2.3 Format Handler — przetwarzanie dokumentów

Odpowiada za:
- **Ekstrakcję** z DOCX: tekst + metadane formatowania (font, bold, kolor)
- **Rekonstrukcję** DOCX: zachowanie oryginalnego layoutu z przetłumaczonym tekstem
- **Post-processing**:
  - Zamiana cudzysłowów na polskie (`„..."`)
  - Twarde spacje przy sierotach (w, i, z, o, a, u)
  - Półpauzy w przedziałach liczbowych (§§ 34–45)
  - Kolorowanie cytowań (opcjonalne)

---

## 3. Workflow tłumaczenia

### Faza 1: Upload i analiza
```
Użytkownik ──► Upload DOCX ──► Structure Parser ──► Segmentacja
                                                        │
                                                        ▼
                                              Statystyki dokumentu
                                              (słowa, segmenty, czas)
```

### Faza 2: Ekstrakcja terminologii (batch)
```
Segment ──► Term Extractor ──► Case Law Researcher ──► TM Manager
                                      │
                                      ▼
                               Terminy z źródłami:
                               - TM exact (confidence 1.0)
                               - HUDOC (0.95)
                               - CURIA (0.90)
                               - IATE (0.85)
                               - AI proposal (0.70)
```

### Faza 3: Tłumaczenie (batch)
```
Segment + Terminy ──► Translator ──► Tłumaczenie
        │                                 │
        │                                 ▼
        │                          WebSocket: segment_translated
        │
        └──► Batch 10 segmentów ──► WebSocket: batch_ready
```

### Faza 4: Walidacja użytkownika (human-in-the-loop)
```
┌─────────────────────────────────────────────────────────────┐
│                    Interfejs walidacji                      │
├─────────────────────────────────────────────────────────────┤
│  Termin EN        │ Propozycja PL    │ Źródło   │ Akcja    │
│  ─────────────────┼──────────────────┼──────────┼────────  │
│  applicant        │ skarżący         │ TM exact │ ✓ ✎ ✗   │
│  margin of        │ margines oceny   │ HUDOC    │ ✓ ✎ ✗   │
│  appreciation     │                  │          │          │
│  Section Registrar│ Kanclerz Sekcji  │ IATE     │ ✓ ✎ ✗   │
└─────────────────────────────────────────────────────────────┘

✓ = zatwierdź    ✎ = edytuj    ✗ = odrzuć
```

### Faza 5: Finalizacja
```
Zatwierdzone terminy ──► Change Implementer ──► Re-tłumaczenie
                                                      │
                                                      ▼
                                              QA Reviewer
                                                      │
                                                      ▼
                                              Format Handler
                                                      │
                                                      ▼
                                              DOCX do pobrania
                                                      │
                                                      ▼
                                              TM update (opcjonalnie)
```

---

## 4. Źródła terminologii

### 4.1 Hierarchia źródeł

| Priorytet | Źródło | Confidence | Opis |
|-----------|--------|------------|------|
| 1 | TM exact | 1.0 | Dokładne dopasowanie z pamięci tłumaczeniowej |
| 2 | TM fuzzy | 0.85-0.99 | Dopasowanie rozmyte (>75% podobieństwa) |
| 3 | HUDOC | 0.95 | Orzecznictwo ETPCz |
| 4 | CURIA | 0.90 | Orzecznictwo TSUE |
| 5 | IATE | 0.85 | Baza terminologii UE |
| 6 | AI proposal | 0.70 | Propozycja Claude bez źródła |

### 4.2 HUDOC — baza orzecznictwa ETPCz

- **URL**: `https://hudoc.echr.coe.int`
- **Zawartość**: Wyroki, decyzje, opinie doradcze ETPCz
- **Wbudowane terminy** (40+):
  ```
  applicant → skarżący
  margin of appreciation → margines oceny
  just satisfaction → słuszne zadośćuczynienie
  fair trial → rzetelny proces
  interference → ingerencja
  ```

### 4.3 CURIA — orzecznictwo TSUE

- **URL**: `https://curia.europa.eu`
- **Zawartość**: Wyroki Trybunału Sprawiedliwości UE
- **Zastosowanie**: Terminologia prawa UE (pomoc publiczna, konkurencja, swobody)

### 4.4 IATE — terminologia instytucji UE

- **URL**: `https://iate.europa.eu`
- **Zawartość**: 8+ milionów terminów w 24 językach
- **Mock fallback** (56+ terminów) gdy API niedostępne:
  ```
  legal certainty → pewność prawa
  proportionality → proporcjonalność
  legitimate expectation → uzasadnione oczekiwanie
  ```

### 4.5 Translation Memory (TM)

- **Format**: TMX 1.4, TBX
- **Funkcje**:
  - Wiele plików TM jednocześnie
  - System priorytetów (1-5)
  - Włączanie/wyłączanie per TM
  - Fuzzy matching (RapidFuzz, próg 0.75)
  - Automatyczna aktualizacja po walidacji

---

## 5. Reguły tłumaczenia ETPCz

### 5.1 Terminologia kluczowa

| Angielski | Polski | Uwagi |
|-----------|--------|-------|
| applicant | skarżący/skarżąca | nie: osoba skarżąca |
| alleged violation | zarzucane naruszenie | nie: domniemane |
| margin of appreciation | margines oceny | nie: uznania |
| fair trial | rzetelny proces | nie: sprawiedliwy |
| final judgment | ostateczny wyrok | nie: prawomocny |
| interference | ingerencja | nie: naruszenie |
| just satisfaction | słuszne zadośćuczynienie | — |
| Registrar | Kanclerz | nie: Sekretarz |
| Section Registrar | Kanclerz Sekcji | nie: Sekretarz Sekcji |
| Registry | Kancelaria Trybunału | — |

### 5.2 Jednostki redakcyjne

| Kontekst | Format | Przykład |
|----------|--------|----------|
| EKPC | art. X ust. Y | art. 8 ust. 1 Konwencji |
| Regulamin Trybunału | Reguła X § Y | Reguła 77 § 1 Regulaminu |
| Paragraf bieżącego wyroku | paragraf (słownie) | paragraf 34 powyżej |
| Paragraf cytowanego wyroku | § (symbol) | § 45 wyroku X p. Y |

### 5.3 Cytowanie orzeczeń

**ETPCz**:
```
✓ w sprawie Reczkowicz przeciwko Polsce (skarga nr 43447/19, §§ 59–70, 22 lipca 2021 r.)
✗ w sprawie Reczkowicz przeciwko Polsce (43447/19, §§ 59-70)
```

**TSUE**:
```
✓ w połączonych sprawach A.K. i inni (C-585/18, C-624/18 i C-625/18)
✗ w połączonych sprawach A.K. i inni (nr C-585/18, nr C-624/18)
```

### 5.4 Interpunkcja polska

- **Cudzysłowy**: „tekst" (nie "tekst")
- **Półpauza w przedziałach**: §§ 34–45 (nie §§ 34-45)
- **Brak przecinka**: „W przypadku gdy" (nie „W przypadku, gdy")
- **Twarde spacje**: w sprawie, 2024 r., art. 5

---

## 6. Interfejs użytkownika

### 6.1 Strona główna — upload dokumentu

- Drag & drop lub wybór pliku DOCX
- Walidacja formatu i rozmiaru (max 50MB)
- Statystyki: liczba słów, segmentów, szacowany czas

### 6.2 Panel tłumaczenia

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Nazwa dokumentu]                    Postęp: ████████░░ 80%        │
├─────────────────────┬───────────────────────────────────────────────┤
│                     │                                               │
│   GLOSARIUSZ        │              PODGLĄD TŁUMACZENIA              │
│                     │                                               │
│  ┌───────────────┐  │  [1] The applicant was born in 1985...       │
│  │ applicant     │  │      Skarżący urodził się w 1985 r....       │
│  │ → skarżący    │  │                                               │
│  │ [TM] ✓        │  │  [2] The Court considers that...             │
│  └───────────────┘  │      Trybunał uznał, że...                    │
│                     │                                               │
│  ┌───────────────┐  │  [3] Having regard to the margin of          │
│  │ margin of     │  │      appreciation enjoyed by States...        │
│  │ appreciation  │  │      Mając na uwadze margines oceny,          │
│  │ → margines    │  │      z którego korzystają Państwa...          │
│  │   oceny       │  │                                               │
│  │ [HUDOC] ✓     │  │                                               │
│  └───────────────┘  │                                               │
│                     │                                               │
├─────────────────────┴───────────────────────────────────────────────┤
│  [Zatwierdź wszystkie]  [Zobacz tłumaczenie]  [Pobierz DOCX]        │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Edytor terminów

- Podgląd kontekstu użycia
- Historia zmian (oryginalna propozycja)
- Odniesienia do orzecznictwa
- Propagacja zmiany do wszystkich segmentów

### 6.4 Raport źródeł

Szczegółowy breakdown terminów według źródła:
- TM exact: 45 terminów (40%)
- HUDOC: 30 terminów (27%)
- CURIA: 15 terminów (13%)
- IATE: 12 terminów (11%)
- AI proposals: 10 terminów (9%)

---

## 7. Deployment

### 7.1 Render.com (produkcja)

```yaml
services:
  - type: web
    name: ecthr-translator-backend
    env: python
    region: frankfurt
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false  # secret
      - key: DATABASE_URL
        value: sqlite:////tmp/data/ecthr.db
```

### 7.2 Docker (lokalne)

```bash
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### 7.3 Vercel (frontend)

- Auto-deploy z brancha `main`
- Environment: `VITE_API_URL=https://backend.render.com`

---

## 8. Metryki i wydajność

| Metryka | Wartość |
|---------|---------|
| Czas tłumaczenia 10-stronowego wyroku | ~15 min (QUICK) / ~45 min (FULL) |
| Średnia dokładność terminologii | 92% (po walidacji: 99%) |
| Segmenty na batch | 10 |
| Timeout Claude API | 120s |
| Retry policy | 5 prób, exponential backoff |
| Max rozmiar dokumentu | 50 MB |
| Max rozmiar TM | 500 MB |

---

## 9. Przyszły rozwój

1. **Więcej par językowych** — DE-PL, FR-PL
2. **Integracja z SDL Trados** — eksport/import SDLXLIFF
3. **Fine-tuning modelu** — dedykowany model na korpusie ETPCz
4. **Wykrywanie zmian prawnych** — alertowanie o nowych wyrokach zmieniających terminologię
5. **Collaborative editing** — współpraca wielu tłumaczy na jednym dokumencie
6. **API publiczne** — integracja z zewnętrznymi systemami kancelarii

---

## 10. Podsumowanie

ECTHR Translator demonstruje praktyczne zastosowanie systemów wieloagentowych AI w domenie wymagającej precyzji — tłumaczeniu prawnym. Kluczowe innowacje:

1. **Hierarchia źródeł wiedzy** — automatyczne wyszukiwanie w orzecznictwie z priorytetyzacją
2. **Human-in-the-loop** — AI proponuje, człowiek decyduje
3. **Domain-specific prompts** — 86 reguł tłumaczenia specyficznych dla ETPCz
4. **Feedback loop** — zatwierdzone terminy wracają do TM
5. **Format fidelity** — zachowanie oryginalnego formatowania DOCX

System pokazuje, że AI może znacząco przyspieszyć pracę tłumaczy specjalistycznych, nie zastępując ich ekspertyzy, lecz wzbogacając ich workflow o automatyczne badanie orzecznictwa i propozycje terminologiczne.

---

**Repozytorium**: [github.com/wojtwol/ecthr-translator](https://github.com/wojtwol/ecthr-translator)

**Technologie**: Python 3.11, FastAPI, React 18, Anthropic Claude, SQLAlchemy, WebSocket

**Licencja**: MIT

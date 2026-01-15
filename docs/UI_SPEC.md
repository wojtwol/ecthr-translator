# UI Specification – ECTHR Translator

## Design System

### Colors
```css
--primary-600: #4F46E5;     /* Indigo – akcje główne */
--success-500: #22C55E;     /* Approved */
--warning-500: #F59E0B;     /* Pending/Fuzzy */
--error-500: #EF4444;       /* Rejected */

/* Source badges */
--tm-exact: #059669;        /* emerald */
--tm-fuzzy: #D97706;        /* amber */
--hudoc: #7C3AED;           /* violet */
--curia: #2563EB;           /* blue */
--proposed: #6B7280;        /* gray */
```

---

## Pages

### 1. Home Page (`/`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚖️ ECTHR Translator                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│            ┌─────────────────────────────────────┐              │
│            │    📄 Przeciągnij plik DOCX         │              │
│            │    lub kliknij aby wybrać           │              │
│            └─────────────────────────────────────┘              │
│                                                                 │
│            Kierunek: [English → Polski    ▼]                    │
│            ☑ Przeszukuj HUDOC                                   │
│            ☑ Przeszukuj CURIA                                   │
│                                                                 │
│            ┌─────────────────────────────────────┐              │
│            │          ▶ ROZPOCZNIJ               │              │
│            └─────────────────────────────────────┘              │
│                                                                 │
│  📚 Ostatnie dokumenty                                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ 📄 case_54321.docx          ✓ Zakończone    14:32     │    │
│  │ 📄 hudoc_12345.docx         ⏳ W trakcie     12:15     │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Translation Page – Validation Phase (`/translation/{id}`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚖️ ECTHR Translator                                            │
├────────────────────┬────────────────────────────────────────────┤
│  GLOSARIUSZ        │  PODGLĄD TŁUMACZENIA                       │
│  ─────────────     │  ───────────────────                       │
│                    │                                            │
│  28/47 ✓           │  Sekcja: [THE LAW           ▼]            │
│  15 oczekujących   │                                            │
│                    │  ┌────────────────────────────────────┐   │
│  ┌──────────────┐  │  │ ŹRÓDŁO                             │   │
│  │ ✓ margin of  │  │  │ The Court reiterates that the     │   │
│  │   appreciat. │  │  │ margin of appreciation afforded   │   │
│  │              │  │  │ to States...                      │   │
│  │   margines   │  │  ├────────────────────────────────────┤   │
│  │   oceny      │  │  │ TŁUMACZENIE                        │   │
│  │              │  │  │ Trybunał przypomina, że           │   │
│  │ 📚 HUDOC     │  │  │ [margines oceny] przyznany        │   │
│  │ ████ 100%    │  │  │ państwom...                       │   │
│  │ [✓] [✎]     │  │  └────────────────────────────────────┘   │
│  └──────────────┘  │                                            │
│                    │                                            │
│  ┌──────────────┐  │                                            │
│  │ ⚠ just      │  │                                            │
│  │   satisfact. │  │                                            │
│  │              │  │                                            │
│  │   słuszne   │  │                                            │
│  │   zadość... │  │                                            │
│  │              │  │                                            │
│  │ 📁 TM fuzzy │  │                                            │
│  │ ███░░ 85%   │  │                                            │
│  │ [✓] [✎]    │  │                                            │
│  └──────────────┘  │                                            │
├────────────────────┴────────────────────────────────────────────┤
│  [ZATWIERDŹ WSZYSTKIE]                    [ZAKOŃCZ WALIDACJĘ ▶]│
└─────────────────────────────────────────────────────────────────┘
```

### 3. Term Editor Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  Edycja terminu                                           [X]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TERMIN ŹRÓDŁOWY                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ just satisfaction                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  PROPOZYCJA SYSTEMU                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ słuszne zadośćuczynienie                    📋 Kopiuj   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  📁 TM fuzzy (85%)                                              │
│                                                                 │
│  TWOJE TŁUMACZENIE                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ słuszne zadośćuczynienie                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ŹRÓDŁA REFERENCYJNE                                            │
│  📚 HUDOC (3)                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • "słuszne zadośćuczynienie" – Tyrer v. UK (1978)       │   │
│  │ • "słuszne zadośćuczynienie" – Handyside v. UK (1976)   │   │
│  │ • "sprawiedliwe zadośćuczynienie" – Sunday Times (1979) │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  📁 Twoja TM (13)                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • "słuszne zadośćuczynienie" – 10 wystąpień             │   │
│  │ • "sprawiedliwe zadośćuczynienie" – 3 wystąpienia       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [ODRZUĆ]              [ANULUJ]          [ZAPISZ I NASTĘPNY ▶] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### FileUpload.jsx
- Drag & drop + click to select
- States: idle, dragover, uploading, error
- Max 50MB, tylko .docx

### GlossaryPanel.jsx
- Scrollable list of terms
- Filter: all / pending / approved / edited / rejected
- Quick approve button per term

### TermCard.jsx
- Source term, target term
- Source badge (TM/HUDOC/CURIA/proposed)
- Confidence bar
- Status indicator

### TermEditor.jsx
- Modal for editing
- Shows references from HUDOC, CURIA, TM
- Context in document

### TranslationPreview.jsx
- Side-by-side source/target
- Highlights active term
- Section filter

### ProgressBar.jsx
- Animated progress
- Phase labels

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | Navigate terms |
| `Enter` | Open editor |
| `A` | Approve term |
| `E` | Edit term |
| `Esc` | Close modal |
| `Ctrl+Enter` | Finalize |

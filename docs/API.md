# API Documentation – ECTHR Translator

## Base URL
```
Local: http://localhost:8000/api
```

---

## Documents

### Upload Document
```http
POST /documents/upload
Content-Type: multipart/form-data

file: <DOCX file>
```

**Response:** `201 Created`
```json
{
    "id": "doc_abc123",
    "filename": "case_12345.docx",
    "status": "uploaded",
    "created_at": "2024-01-15T10:30:00Z"
}
```

### Get Document Status
```http
GET /documents/{document_id}
```

**Response:** `200 OK`
```json
{
    "id": "doc_abc123",
    "filename": "case_12345.docx",
    "status": "translating",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:35:00Z"
}
```

**Status values:** `uploaded`, `analyzing`, `translating`, `validating`, `completed`, `error`

### Download Translated Document
```http
GET /documents/{document_id}/download
```

**Response:** `200 OK` (DOCX file)

---

## Translation

### Start Translation
```http
POST /translation/{document_id}/start
Content-Type: application/json

{
    "config": {
        "language_pair": "EN-PL",
        "use_hudoc": true,
        "use_curia": true,
        "fuzzy_threshold": 0.75
    }
}
```

**Response:** `202 Accepted`
```json
{
    "job_id": "job_xyz789",
    "document_id": "doc_abc123",
    "status": "started",
    "phase": "analysis"
}
```

### Get Translation Status
```http
GET /translation/{document_id}/status
```

**Response:** `200 OK`
```json
{
    "job_id": "job_xyz789",
    "status": "in_progress",
    "phase": "translating",
    "progress": 0.65,
    "current_step": "Translating segment 23/35...",
    "stats": {
        "segments_total": 35,
        "segments_translated": 23,
        "terms_extracted": 47
    }
}
```

**Phases:** `analysis` (0-20%), `term_extraction` (20-40%), `research` (40-50%), `translating` (50-90%), `validation` (90%), `implementing` (90-95%), `qa` (95-100%), `completed` (100%)

### Finalize Translation
```http
POST /translation/{document_id}/finalize
```

---

## Glossary

### Get Terms List
```http
GET /glossary/{document_id}?status=all&page=1&per_page=50
```

**Response:** `200 OK`
```json
{
    "total": 47,
    "stats": {
        "pending": 15,
        "approved": 28,
        "edited": 3,
        "rejected": 1
    },
    "terms": [
        {
            "id": "term_001",
            "source_term": "margin of appreciation",
            "target_term": "margines oceny",
            "source_type": "hudoc",
            "confidence": 1.0,
            "status": "approved",
            "references": [
                {
                    "source": "hudoc",
                    "case_name": "Handyside v. UK",
                    "url": "https://hudoc.echr.coe.int/..."
                }
            ],
            "occurrences": 5
        }
    ]
}
```

### Update Term
```http
PUT /glossary/{document_id}/{term_id}
Content-Type: application/json

{
    "target_term": "słuszne zadośćuczynienie",
    "status": "approved"
}
```

### Approve All Pending
```http
POST /glossary/{document_id}/approve-all
```

---

## Preview

### Get Translation Preview
```http
GET /preview/{document_id}?highlight_term_id=term_002
```

**Response:** `200 OK`
```json
{
    "segments": [
        {
            "id": "seg_015",
            "section_type": "operative",
            "source_text": "The Court awards EUR 5,000 in respect of just satisfaction.",
            "target_text": "Trybunał przyznaje 5 000 EUR tytułem <mark data-term-id=\"term_002\">słusznego zadośćuczynienia</mark>.",
            "terms_used": [{"term_id": "term_002", "position": {"start": 52, "end": 76}}]
        }
    ]
}
```

---

## WebSocket

```
WS /ws/translation/{document_id}
```

**Messages:**
```json
{"type": "progress", "phase": "translating", "progress": 0.65, "current_step": "..."}
{"type": "term_found", "term": {...}}
{"type": "phase_complete", "phase": "translation", "next_phase": "validation"}
{"type": "completed", "translated_path": "/outputs/doc_abc123_PL.docx"}
{"type": "error", "message": "..."}
```

---

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `DOCUMENT_NOT_FOUND` | 404 | Document doesn't exist |
| `INVALID_FILE_FORMAT` | 400 | Not a valid DOCX |
| `TRANSLATION_IN_PROGRESS` | 409 | Already running |
| `HUDOC_UNAVAILABLE` | 503 | HUDOC temporarily down |

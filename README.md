# ECTHR Translator

Legal terminology translation API with **real integrations** for HUDOC, CURIA, and IATE databases.

## Features

- **HUDOC Integration**: Real search in European Court of Human Rights case law database
- **CURIA Integration**: Real access to CJEU case law via EUR-Lex SPARQL endpoint
- **IATE Integration**: Official API access to Interactive Terminology for Europe database
- **Multi-source search**: Automatically searches across all enabled databases
- **Intelligent selection**: Chooses best translation based on source reliability and confidence
- **Batch processing**: Search multiple terms simultaneously
- **RESTful API**: Clean FastAPI-based REST API with OpenAPI documentation

## Architecture

```
backend/
├── services/         # Database client implementations
│   ├── hudoc_client.py    # HUDOC web scraping/search
│   ├── curia_client.py    # EUR-Lex SPARQL queries
│   └── iate_client.py     # IATE API integration
├── agents/           # Business logic
│   └── case_law_researcher.py  # Multi-source coordinator
├── routers/          # API endpoints
│   └── terminology.py
├── models/           # Pydantic models
│   └── api_models.py
├── config.py         # Configuration
└── main.py          # FastAPI application
```

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ecthr-translator
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

## Configuration

### Database Settings

The application can work in two modes for each database:

1. **Real API mode** (recommended): Set `*_USE_MOCK=False` in `.env`
2. **Mock mode** (fallback): Set `*_USE_MOCK=True` in `.env`

### HUDOC (ECHR)

- No API credentials required
- Uses web scraping and search URL construction
- Automatically enabled by default

### CURIA (CJEU via EUR-Lex)

- No API credentials required
- Uses public SPARQL endpoint
- Automatically enabled by default

### IATE

- **Requires API credentials** for full functionality
- Contact `iate@cdt.europa.eu` to obtain API keys
- Add credentials to `.env`:
  ```
  IATE_USERNAME=your_username
  IATE_API_KEY=your_api_key
  ```
- Falls back to mock mode if credentials not provided

## Running the Application

### Development mode

```bash
# From project root
python -m backend.main

# Or with uvicorn directly
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Production mode

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Usage

### Search single term

```bash
curl -X POST "http://localhost:8000/api/terminology/search" \
  -H "Content-Type: application/json" \
  -d '{
    "term": "margin of appreciation",
    "source_lang": "en",
    "target_lang": "pl"
  }'
```

Response:
```json
{
  "term": "margin of appreciation",
  "best_translation": "margines oceny",
  "best_confidence": 0.95,
  "best_source": "iate",
  "all_results": [
    {
      "source": "hudoc",
      "translation": "margines oceny",
      "confidence": 0.9,
      "references": ["Handyside v. United Kingdom"],
      "domain": null
    },
    {
      "source": "iate",
      "translation": "margines oceny",
      "confidence": 0.95,
      "references": ["IATE:9012345"],
      "domain": "ECHR"
    }
  ]
}
```

### Search batch

```bash
curl -X POST "http://localhost:8000/api/terminology/search/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "terms": ["legal certainty", "proportionality", "direct effect"],
    "source_lang": "en",
    "target_lang": "pl"
  }'
```

### Check health

```bash
curl http://localhost:8000/api/terminology/health
```

### Get available sources

```bash
curl http://localhost:8000/api/terminology/sources
```

## Real vs Mock Mode

### Current Implementation Status

| Database | Real API | Status | Requirements |
|----------|----------|--------|-------------|
| HUDOC | ✅ Implemented | Web scraping | None |
| CURIA | ✅ Implemented | SPARQL queries | None |
| IATE | ⚠️ Partial | API ready | API credentials needed |

### Enabling Real Mode

Edit `.env` file:

```bash
# Enable real HUDOC searches
HUDOC_USE_MOCK=False

# Enable real CURIA searches via EUR-Lex
CURIA_USE_MOCK=False

# Enable real IATE searches (requires credentials)
IATE_USE_MOCK=False
IATE_USERNAME=your_username
IATE_API_KEY=your_api_key
```

### Obtaining IATE Credentials

1. Visit: https://iate.europa.eu/
2. Contact: iate@cdt.europa.eu
3. Request API access for your project
4. Add credentials to `.env` file

## Development

### Running tests

```bash
pytest tests/ -v
```

### Code structure

- `services/`: Low-level database clients
- `agents/`: High-level business logic
- `routers/`: API endpoint handlers
- `models/`: Request/response models
- `config.py`: Centralized configuration

## Troubleshooting

### HUDOC not returning translations

HUDOC search primarily returns case references. Translation extraction requires:
1. Fetching individual case documents
2. Parsing bilingual content
3. NLP extraction of term translations

Current implementation returns case references. Full translation extraction can be added.

### CURIA/EUR-Lex SPARQL queries timing out

- Increase `CURIA_TIMEOUT_SECONDS` in `.env`
- Simplify SPARQL queries
- Use mock mode as fallback

### IATE authentication errors

- Verify credentials in `.env`
- Check if API key is still valid
- Contact iate@cdt.europa.eu for support
- Use mock mode as temporary fallback

## Sources & Documentation

- **HUDOC**: https://hudoc.echr.coe.int/
- **EUR-Lex SPARQL**: https://publications.europa.eu/webapi/rdf/sparql
- **IATE**: https://iate.europa.eu/
- **IATE API Docs**: https://documenter.getpostman.com/view/4028985/RztoMTwn

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

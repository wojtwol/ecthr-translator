# ECTHR Translator

Legal terminology translation API with **real integrations** for HUDOC, CURIA, and IATE databases.

## Features

- **HUDOC Integration**: Real search in European Court of Human Rights case law database ✅
- **CURIA Integration**: Real access to CJEU case law via EUR-Lex SPARQL endpoint ✅
- **IATE Integration**: Real PUBLIC API - NO credentials required! ✅ 🎉
- **Multi-source search**: Automatically searches across all enabled databases
- **Intelligent selection**: Chooses best translation based on source reliability and confidence
- **Batch processing**: Search multiple terms simultaneously
- **RESTful API**: Clean FastAPI-based REST API with OpenAPI documentation
- **Zero-config**: Works out of the box - no API keys needed!

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

- **PUBLIC API** - NO credentials required! ✅
- Works out of the box with public endpoint: `https://iate.europa.eu/em-api/entries/_search`
- Optional OAuth credentials available from `iate@cdt.europa.eu` for advanced features
- Credentials can be added to `.env` (optional):
  ```
  IATE_USERNAME=your_username
  IATE_API_KEY=your_api_key
  ```

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

## Deployment

### Deploy to Render (Recommended) ⭐

**Render is perfect for FastAPI!** Free tier available, auto-deploy from GitHub.

#### Option 1: One-Click Deploy

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` and configure everything!
5. Click **"Create Web Service"**

**Done!** Your API will be live at `https://your-app.onrender.com`

#### Option 2: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `ecthr-translator`
   - **Region**: Frankfurt (closest to EU databases)
   - **Branch**: `main` or your branch
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables** (optional):
   ```
   HUDOC_USE_MOCK=false
   CURIA_USE_MOCK=false
   IATE_USE_MOCK=false
   ```
6. Click **"Create Web Service"**

**Your API will be live in ~2 minutes!** 🚀

#### Free Tier Limitations

- Service spins down after 15 min of inactivity
- First request after sleep takes ~30 seconds
- Perfect for development and testing!

### Deploy to Vercel

Vercel is primarily for frontends, but FastAPI can work:

1. Go to [Vercel Dashboard](https://vercel.com)
2. Import your GitHub repository
3. **Settings** → **General** → **Root Directory**: Leave EMPTY (remove "frontend")
4. The `vercel.json` file will handle the rest
5. Deploy!

**Note**: Render is recommended for better FastAPI support.

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
| IATE | ✅ Implemented | Public API | **None!** |

### Enabling Real Mode

Edit `.env` file:

```bash
# Enable real HUDOC searches
HUDOC_USE_MOCK=False

# Enable real CURIA searches via EUR-Lex
CURIA_USE_MOCK=False

# Enable real IATE searches (NO CREDENTIALS NEEDED!)
IATE_USE_MOCK=False
```

**All three databases now work with real APIs out of the box!** 🎉

### Optional: IATE OAuth Credentials

For advanced IATE features, you can optionally obtain OAuth credentials:

1. Visit: https://iate.europa.eu/developers
2. Contact: iate@cdt.europa.eu
3. Request OAuth credentials for advanced features
4. Add credentials to `.env` file (optional)

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

### IATE connection errors

- Check internet connectivity
- Verify endpoint: `https://iate.europa.eu/em-api/entries/_search`
- Increase `IATE_TIMEOUT_SECONDS` in `.env`
- Check IATE service status
- Use mock mode as temporary fallback (`IATE_USE_MOCK=True`)

## Sources & Documentation

- **HUDOC**: https://hudoc.echr.coe.int/
- **EUR-Lex SPARQL**: https://publications.europa.eu/webapi/rdf/sparql
- **IATE**: https://iate.europa.eu/
- **IATE Developers**: https://iate.europa.eu/developers
- **IATE Search API Docs**: https://documenter.getpostman.com/view/4028985/RztoMTwn
- **IATE Auth API Docs**: https://documenter.getpostman.com/view/4028985/S1Lr2pzQ

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

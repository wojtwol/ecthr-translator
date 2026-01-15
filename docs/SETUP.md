# Setup Guide – ECTHR Translator

## Wymagania
- Docker Desktop 4.0+
- 8 GB RAM (16 GB zalecane)
- Klucz API Anthropic

## Instalacja

### 1. Klonowanie
```bash
git clone https://github.com/[user]/ecthr-translator.git
cd ecthr-translator
```

### 2. Konfiguracja
```bash
cp .env.example .env
# Edytuj .env i dodaj ANTHROPIC_API_KEY
```

### 3. Uruchomienie
```bash
docker-compose up --build
```

### 4. Dostęp
```
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

## Konfiguracja TM

### Import z SDL Trados
1. File → Export → TMX
2. Zapisz jako `./data/tm/trados_export.tmx`

### Import z CSV
```csv
source,target,domain
"margin of appreciation","margines oceny","ecthr"
"just satisfaction","słuszne zadośćuczynienie","ecthr"
```

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Sprawdź czy plik `.env` istnieje i zawiera klucz

### "Port 8000 already in use"
Zmień BACKEND_PORT w .env

### "HUDOC timeout"
HUDOC może być czasowo niedostępny, system ponowi próbę

# 🚀 ECTHR Translator - Uruchomienie

## ⚡ Szybki start (lokalnie na swoim komputerze)

### Opcja 1: Docker Compose (POLECANE - 1 komenda)

```bash
# 1. Sklonuj repozytorium
git clone <repo-url>
cd ecthr-translator

# 2. Skopiuj i edytuj .env
cp .env.example .env
nano .env  # Dodaj swój ANTHROPIC_API_KEY

# 3. Uruchom
docker-compose up -d

# 4. Otwórz w przeglądarce
http://localhost:3000
```

**To wszystko!** 🎉

### Opcja 2: Bez Dockera

```bash
# 1. Sklonuj repo
git clone <repo-url>
cd ecthr-translator

# 2. Skopiuj .env
cp .env.example .env
nano .env  # Dodaj ANTHROPIC_API_KEY

# 3. Uruchom skrypt
chmod +x start.sh
./start.sh

# 4. Otwórz
http://localhost:3000
```

## 🛑 Zatrzymywanie

```bash
# Docker:
docker-compose down

# Bez Dockera:
./stop.sh
```

## 📦 Co zawiera Docker Compose

- **Frontend** (React + Vite): Port 3000
- **Backend** (FastAPI): Port 8000
- **Database** (PostgreSQL): Port 5432 (wewnętrzny)

## 🔧 Wymagania

- Docker + Docker Compose **LUB**
- Python 3.11+ i Node.js 18+
- ANTHROPIC_API_KEY (z https://console.anthropic.com/)

## 📖 Dokumentacja API

Po uruchomieniu: http://localhost:8000/docs

## ⚖️ Funkcje

- ✅ Sprint 1: Segment Translator
- ✅ Sprint 2: Term Extractor
- ✅ Sprint 3: Case Law Researcher (HUDOC + CURIA)
- ✅ Sprint 4: Human-in-the-loop Validator
- ✅ Sprint 5: Change Implementer + QA Reviewer + TM Auto-update

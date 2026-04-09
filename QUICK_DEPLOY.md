# 🚀 Szybki Deploy - 5 minut

## ✅ KROK 1: Backend na Render.com (2 min) - DARMOWY

### 1. Załóż konto
- Idź na **https://render.com**
- Kliknij **"Get Started for Free"**
- Zaloguj się przez **GitHub**

### 2. Stwórz Web Service
1. Na dashboard kliknij **"New +"** → **"Web Service"**
2. Kliknij **"Connect account"** żeby połączyć GitHub (jeśli jeszcze nie)
3. Znajdź i wybierz repo: **wojtwol/ecthr-translator**
4. Kliknij **"Connect"**

### 3. Konfiguracja
Wypełnij formularz:

- **Name:** `ecthr-translator-backend` (lub cokolwiek)
- **Region:** Frankfurt (najbliżej Polski)
- **Branch:** `claude/new-conversation-m5W8H`
- **Root Directory:** `backend`
- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 4. Dodaj zmienne środowiskowe
Przewiń w dół do **"Environment Variables"** i dodaj:

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` (twój klucz z Claude) |
| `TM_PATH` | `/opt/render/project/src/data/tm` |
| `UPLOAD_PATH` | `/opt/render/project/src/data/uploads` |
| `OUTPUT_PATH` | `/opt/render/project/src/data/outputs` |

### 5. Deploy!
- Wybierz **Free plan** (0 USD)
- Kliknij **"Create Web Service"**
- Poczekaj 2-3 minuty (Render zbuduje backend)

### 6. Skopiuj URL backendu
Po deploy zobaczysz URL typu:
```
https://ecthr-translator-backend.onrender.com
```
**ZAPISZ TEN URL!** Potrzebujesz go w następnym kroku.

---

## ✅ KROK 2: Frontend na Vercel (2 min) - DARMOWY

### 1. Załóż konto
- Idź na **https://vercel.com**
- Kliknij **"Sign Up"**
- Zaloguj się przez **GitHub**

### 2. Import projektu
1. Na dashboard kliknij **"Add New..."** → **"Project"**
2. Znajdź repo: **wojtwol/ecthr-translator**
3. Kliknij **"Import"**

### 3. Konfiguracja
Wypełnij formularz:

- **Project Name:** `ecthr-translator` (lub cokolwiek)
- **Framework Preset:** Vite
- **Root Directory:** Kliknij **"Edit"** → wpisz `frontend`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`

### 4. Dodaj zmienną środowiskową
Przewiń do **"Environment Variables"**:

| Key | Value |
|-----|-------|
| `VITE_API_URL` | `https://ecthr-translator-backend.onrender.com/api` |

⚠️ **WAŻNE:** Użyj URL backendu z Kroku 1.6 + `/api` na końcu!

### 5. Deploy!
- Kliknij **"Deploy"**
- Poczekaj 1-2 minuty

---

## 🎉 GOTOWE!

Vercel pokaże Ci URL typu:
```
https://ecthr-translator.vercel.app
```

**Kliknij i aplikacja działa!** ✅

---

## 📝 Ważne informacje

### ⚠️ Free tier Render
- Backend **śpi po 15 minutach** bez użycia
- Pierwsze uruchomienie po śnie zajmuje ~30 sekund
- Idealny do testów i demo

### 🔄 Auto-deployment
Każdy push do brancha `claude/new-conversation-m5W8H` automatycznie:
- ✅ Przebuduje backend na Render
- ✅ Przebuduje frontend na Vercel

### 🔑 Gdzie wziąć ANTHROPIC_API_KEY?
1. Idź na https://console.anthropic.com
2. Zaloguj się
3. Settings → API Keys → Create Key
4. Skopiuj klucz (zaczyna się od `sk-ant-api03-...`)

---

## 🐛 Troubleshooting

### Backend nie startuje?
- Sprawdź logi w Render dashboard → Logs
- Upewnij się że `ANTHROPIC_API_KEY` jest dodany

### Frontend nie łączy się z backendem?
- Sprawdź czy `VITE_API_URL` w Vercel ma poprawny URL
- URL powinien kończyć się na `/api`
- Redeploy frontend po zmianie zmiennej (Deployments → ⋯ → Redeploy)

### Backend budzi się długo?
- To normalne na free tieru Render (15-30 sekund)
- Paid plan ($7/mies) nie usypia backendu

---

## 💰 Koszty

- **Render Free:** 750h/miesiąc za darmo (wystarczy na stałe działanie)
- **Vercel Free:** Nieograniczone deployments
- **Razem:** 0 USD 🎉

---

## ❓ Potrzebujesz pomocy?

Wszystko opisane krok po kroku. Po prostu postępuj zgodnie z instrukcją!

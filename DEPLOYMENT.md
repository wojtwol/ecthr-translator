# 🚀 Deployment Guide - Vercel + Railway

## Krok 1: Deploy Backend na Railway (2 minuty)

### 1.1 Załóż konto Railway
- Idź na https://railway.app
- Zaloguj się przez GitHub

### 1.2 Stwórz nowy projekt
1. Kliknij **"New Project"**
2. Wybierz **"Deploy from GitHub repo"**
3. Wybierz repo: `wojtwol/ecthr-translator`
4. Wybierz branch: `claude/new-conversation-m5W8H`

### 1.3 Skonfiguruj zmienne środowiskowe
W Railway dashboard dodaj:
```
ANTHROPIC_API_KEY=twoj-klucz-z-claude
TM_PATH=/app/data/tm
UPLOAD_PATH=/app/data/uploads
OUTPUT_PATH=/app/data/outputs
```

### 1.4 Ustaw root directory
- Settings → Root Directory: `backend`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 1.5 Skopiuj URL backendu
Po deployment Railway da ci URL typu: `https://ecthr-translator-backend.railway.app`
**Zapisz ten URL!**

---

## Krok 2: Deploy Frontend na Vercel (2 minuty)

### 2.1 Załóż konto Vercel
- Idź na https://vercel.com
- Zaloguj się przez GitHub

### 2.2 Import projektu
1. Kliknij **"Add New Project"**
2. Import z GitHub: `wojtwol/ecthr-translator`
3. Branch: `claude/new-conversation-m5W8H`

### 2.3 Konfiguracja
- **Root Directory:** `frontend`
- **Framework Preset:** Vite
- **Build Command:** `npm run build`
- **Output Directory:** `dist`

### 2.4 Dodaj zmienną środowiskową
W Vercel dashboard → Settings → Environment Variables:
```
VITE_API_URL = https://twoj-backend-url.railway.app/api
```
*(użyj URL z Kroku 1.5)*

### 2.5 Deploy!
Kliknij **"Deploy"** - Vercel automatycznie zbuduje i wdroży.

---

## Krok 3: Gotowe! 🎉

Vercel da Ci URL typu:
```
https://ecthr-translator.vercel.app
```

**Otwórz w przeglądarce i testuj!**

---

## 🔄 Auto-deployment

Od teraz każdy push do brancha `claude/new-conversation-m5W8H` automatycznie wdroży zmiany na:
- ✅ Railway (backend)
- ✅ Vercel (frontend)

---

## 🆓 Koszty

- **Vercel:** Darmowy plan (wystarczy dla testów)
- **Railway:** $5/miesiąc kredytów za darmo (wystarczy na ~500h pracy)

---

## ⚙️ Alternatywa: Render.com (zamiast Railway)

Jeśli wolisz Render:
1. Idź na https://render.com
2. New → Web Service
3. Connect GitHub repo
4. Root Directory: `backend`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Dodaj zmienne środowiskowe (jak w Railway)

---

## 🐛 Debug

### Backend nie startuje?
Sprawdź logi w Railway/Render dashboard.

### Frontend nie łączy się z backendem?
1. Sprawdź czy `VITE_API_URL` w Vercel jest poprawny
2. Redeploy frontend po zmianie zmiennej

### CORS errors?
Backend już ma CORS skonfigurowany w `main.py` - powinno działać.

---

## 📞 Potrzebujesz pomocy?

- Railway docs: https://docs.railway.app
- Vercel docs: https://vercel.com/docs
- Render docs: https://render.com/docs

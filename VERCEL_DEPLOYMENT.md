# Deployment na Vercel - Instrukcja krok po kroku

## Wymagania
- Konto na [Vercel](https://vercel.com)
- Repozytorium GitHub: `wojtwol/ecthr-translator`

## Sposób 1: Przez Dashboard Vercel (ZALECANE)

### 1. Połącz repozytorium z Vercel

1. Wejdź na https://vercel.com/dashboard
2. Kliknij **"Add New..."** → **"Project"**
3. Wybierz **"Import Git Repository"**
4. Znajdź i wybierz repozytorium `wojtwol/ecthr-translator`
5. Kliknij **"Import"**

### 2. Skonfiguruj projekt

W ustawieniach projektu ustaw:

**Framework Preset:** `Vite`

**Root Directory:** `frontend` ⚠️ **TO JEST KLUCZOWE!**

**Build & Development Settings:**
- Build Command: `npm run build`
- Output Directory: `dist`
- Install Command: `npm install`

**Environment Variables:**
```
VITE_API_URL=https://ecthr-translator-backend.onrender.com/api
```

### 3. Ustaw Production Branch

**WAŻNE:** Domyślnie Vercel deployuje z brancha `main`, ale ten projekt używa brancha sesyjnego.

1. Po utworzeniu projektu wejdź w **Settings** → **Git**
2. W sekcji **"Production Branch"** zmień z `main` na:
   ```
   claude/continue-new-thread-Twuij
   ```
3. Kliknij **"Save"**

### 4. Deploy

1. Wróć do zakładki **"Deployments"**
2. Kliknij **"Redeploy"** albo poczekaj na automatyczny deployment
3. Po kilku minutach aplikacja będzie dostępna pod adresem typu:
   ```
   https://ecthr-translator-xxx.vercel.app
   ```

---

## Sposób 2: Przez Vercel CLI

### 1. Zainstaluj Vercel CLI

```bash
npm install -g vercel
```

### 2. Zaloguj się

```bash
vercel login
```

### 3. Deploy z folderu frontend

```bash
cd frontend
vercel --prod
```

Postępuj zgodnie z instrukcjami w terminalu.

---

## Troubleshooting

### Problem: "Error: No framework detected"

**Rozwiązanie:** Upewnij się, że Root Directory jest ustawiony na `frontend`

### Problem: "Build failed"

**Rozwiązanie:** Sprawdź czy:
1. Node.js version w Vercel jest ustawiony na 18.x lub nowszy
2. Environment variable `VITE_API_URL` jest poprawnie ustawiony
3. Build Command to `npm run build`, nie `vite build`

### Problem: "404 Not Found" po załadowaniu strony

**Rozwiązanie:** Dodaj `vercel.json` w folderze `frontend/` z następującą konfiguracją:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

### Problem: Backend nie odpowiada

**Rozwiązanie:**
1. Sprawdź czy backend na Render.com działa: https://ecthr-translator-backend.onrender.com/health
2. Sprawdź czy VITE_API_URL w Environment Variables jest poprawny
3. Upewnij się że backend akceptuje requesty CORS z domeny Vercel

---

## Weryfikacja deploymentu

Po deploymencie sprawdź:

1. ✅ Frontend ładuje się poprawnie
2. ✅ Console (F12) nie pokazuje błędów 404 lub CORS
3. ✅ API calls trafiają do `https://ecthr-translator-backend.onrender.com/api/*`
4. ✅ Możesz przesłać plik i otrzymać tłumaczenie

---

## Synchronizacja z Backend

Backend na Render.com jest skonfigurowany do deployowania z tego samego brancha:
- **Branch:** `claude/continue-new-thread-Twuij`
- **Config:** `render.yaml`

Każdy push do tego brancha automatycznie:
- ✅ Deployuje backend na Render.com
- ✅ Deployuje frontend na Vercel (jeśli Production Branch jest poprawnie ustawiony)

---

## Gotowe przykłady

**Backend (Render.com):**
```
https://ecthr-translator-backend.onrender.com
```

**Frontend (Vercel):**
```
https://ecthr-translator.vercel.app
```
(Twój URL może się różnić)

---

## Dodatkowe zasoby

- [Vercel Documentation - Framework Preset](https://vercel.com/docs/frameworks)
- [Vercel Documentation - Git Integration](https://vercel.com/docs/deployments/git)
- [Vite Deployment Guide](https://vitejs.dev/guide/static-deploy.html)

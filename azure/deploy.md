# Hanco-AI — Deployment Guide (Azure)

This document describes how the entire Hanco-AI application is deployed on Microsoft Azure,
how to reproduce the deployment from scratch, how to ship updates, and how to run it locally.

It **replaces the previous AWS App Runner setup** (`/Dockerfile`, `/apprunner/`). Those files
are left in the repo for reference but are no longer used.

---

## 1. Architecture

The app is split into three runtime pieces plus the unchanged database:

```
                         ┌──────────────────────────────────────────────┐
  Browser ── HTTPS ─────►│  Azure Static Web Apps (Free)                 │
                         │  hanco-frontend                                │
                         │  React build + CDN + free SSL + SPA routing    │
                         └───────────────┬───────────────────────────────┘
                                         │  calls  ${VITE_API_BASE_URL}/api/v1/*
                                         ▼
                         ┌──────────────────────────────────────────────┐
                         │  Azure Container Apps (Consumption)            │
                         │  hanco-backend  — FastAPI / uvicorn :8000      │
                         │  scale-to-zero (min 0 / max 2)                 │
                         │  ENABLE_SCHEDULER=false                        │
                         └───────────────┬───────────────────────────────┘
                                         │
                         ┌───────────────┴───────────────────────────────┐
                         │  Azure Container Apps Job (cron, daily)        │
                         │  hanco-scraper — python -m                     │
                         │     app.workers.scrape_competitors             │
                         │  cron "0 0 * * *" UTC  (= 03:00 Riyadh)        │
                         └───────────────┬───────────────────────────────┘
                                         ▼
                         ┌──────────────────────────────────────────────┐
                         │  Firebase Firestore (Spark, free) — hanco-ai  │
                         │  unchanged; both API and Job read/write it     │
                         └──────────────────────────────────────────────┘

  Image source for both backend + scraper:
  Azure Container Registry (Basic)  →  hancoaiacr14734.azurecr.io/hanco-backend:latest
```

Why this shape:
- **Static Web Apps** is free and purpose-built for an SPA — it takes over the static-file
  serving + SPA fallback that nginx did in the old App Runner image.
- **Container Apps (scale-to-zero)** runs the existing backend container but costs ~nothing when idle.
- The backend's in-process APScheduler can't run under scale-to-zero, so scraping was moved to a
  **separate cron Job** (`ENABLE_SCHEDULER=false` disables the in-process scheduler).
- **Firestore stays** — no data migration, no cost.

---

## 2. Resource inventory

Subscription: **Azure subscription 1** (`06f0895e-21f3-4dec-a506-5ece0531436b`)
Resource group: **`hanco-ai-rg`**  ·  Region: **West Europe**

| Component       | Azure service                          | Name              | Public URL / detail |
|-----------------|----------------------------------------|-------------------|---------------------|
| Frontend        | Static Web App (Free)                  | `hanco-frontend`  | https://purple-moss-033b58e03.7.azurestaticapps.net |
| Backend API     | Container App (Consumption, min 0/max 2)| `hanco-backend`  | https://hanco-backend.salmonfield-80a17021.westeurope.azurecontainerapps.io |
| Scraper         | Container Apps Job (cron `0 0 * * *`)  | `hanco-scraper`   | runs `python -m app.workers.scrape_competitors` |
| Container env   | Container Apps Environment             | `hanco-env`       | hosts both app + job |
| Image registry  | Azure Container Registry (Basic)       | `hancoaiacr14734` | `hancoaiacr14734.azurecr.io` — **only paid resource (~$5/mo)** |
| Database        | Firebase Firestore (Spark)             | project `hanco-ai`| external to Azure, free |

---

## 3. Prerequisites

- **Azure CLI** (`az`) ≥ 2.87, logged in: `az login`
- **containerapp** CLI extension: `az extension add -n containerapp` (auto-installs on first use)
- **Node.js** ≥ 18 + npm (to build the frontend)
- Azure resource providers registered (one-time):
  ```bash
  az provider register -n Microsoft.App
  az provider register -n Microsoft.OperationalInsights
  ```
- **Secrets you must supply** (not stored in the repo):
  - Firebase **service-account JSON** (Firebase Console → Project Settings → Service accounts →
    Generate new private key). In this repo it lives gitignored at
    `backend/hanco-ai-firebase-adminsdk-fbsvc-ff8eaf8fd1.json`.
  - `OPENAI_API_KEY` (chatbot fallback) and/or `GEMINI_API_KEY` (chatbot primary).
- Docker is **not** required — images are built in the cloud with `az acr build`.

---

## 4. Application-code changes made for Azure

These were required to make the app deployable in this topology:

| File | Change |
|------|--------|
| `backend/app/main.py` | In-process APScheduler now gated behind `ENABLE_SCHEDULER` (default `false`). Scraping runs via the cron Job instead. |
| `backend/Dockerfile` | Removed `playwright install-deps chromium` (referenced obsolete Debian font packages and broke the build); system libs are already installed manually. |
| `frontend/src/lib/api.ts` | **Created** — was missing from the repo; axios client with `baseURL = ${VITE_API_BASE_URL}/api/v1`, guest-id + Firebase token headers. |
| `frontend/src/lib/firebase.ts` | **Created** — was missing; initializes Firebase web SDK from `VITE_FIREBASE_*`, exports `auth`. |
| `frontend/staticwebapp.config.json` | SPA fallback routing for Static Web Apps. |
| `frontend/.env.production` | Build-time config: backend URL + Firebase web config. |

---

## 5. Full provisioning runbook (from scratch)

Run these in order. They are idempotent enough to re-run individual steps.

### 5.0 Variables
```bash
RG=hanco-ai-rg
LOC=westeurope
ACR=hancoaiacr$RANDOM          # globally-unique; record the value you get
ENV=hanco-env
FB=backend/hanco-ai-firebase-adminsdk-fbsvc-ff8eaf8fd1.json   # your service-account JSON
```

### 5.1 Resource group + registry
```bash
az group create -n "$RG" -l "$LOC"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true
```

### 5.2 Build the backend image in the cloud
```bash
az acr build -r "$ACR" -t hanco-backend:latest -f backend/Dockerfile backend
```

### 5.3 Container Apps environment
```bash
az containerapp env create -n "$ENV" -g "$RG" -l "$LOC"
```

### 5.4 Backend Container App (scale-to-zero)
```bash
ACR_SERVER="$ACR.azurecr.io"
ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query "passwords[0].value" -o tsv)
CRON_SECRET=$(openssl rand -hex 24)
OPENAI_KEY="<your-openai-key>"
FIREBASE_JSON=$(python3 -c "import json;print(json.dumps(json.load(open('$FB'))))")

az containerapp create \
  -n hanco-backend -g "$RG" --environment "$ENV" \
  --image "$ACR_SERVER/hanco-backend:latest" \
  --registry-server "$ACR_SERVER" --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
  --target-port 8000 --ingress external \
  --min-replicas 0 --max-replicas 2 --cpu 0.5 --memory 1.0Gi \
  --secrets firebase-creds="$FIREBASE_JSON" openai-key="$OPENAI_KEY" cron-secret="$CRON_SECRET" \
  --env-vars ENVIRONMENT=production DEBUG=false ENABLE_SCHEDULER=false \
             USE_MOCK_FIREBASE=false FIREBASE_PROJECT_ID=hanco-ai \
             FIREBASE_CREDENTIALS_JSON=secretref:firebase-creds \
             OPENAI_API_KEY=secretref:openai-key CRON_SECRET=secretref:cron-secret

# Record the backend URL:
BACKEND_URL="https://$(az containerapp show -n hanco-backend -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
echo "$BACKEND_URL"
```

### 5.5 Scraper cron Job
```bash
az containerapp job create \
  -n hanco-scraper -g "$RG" --environment "$ENV" \
  --trigger-type Schedule --cron-expression "0 0 * * *" \
  --image "$ACR_SERVER/hanco-backend:latest" \
  --registry-server "$ACR_SERVER" --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
  --cpu 1.0 --memory 2.0Gi \
  --replica-timeout 3600 --replica-retry-limit 1 --parallelism 1 --replica-completion-count 1 \
  --secrets firebase-creds="$FIREBASE_JSON" \
  --env-vars ENVIRONMENT=production FIREBASE_PROJECT_ID=hanco-ai \
             FIREBASE_CREDENTIALS_JSON=secretref:firebase-creds COMPETITOR_SCRAPE_MODE=FULL_GRID \
  --command "python -m app.workers.scrape_competitors"
```
> Note: Container Apps cron is **UTC**. `0 0 * * *` = 03:00 Asia/Riyadh.

### 5.6 Frontend Static Web App
```bash
az staticwebapp create -n hanco-frontend -g "$RG" -l "$LOC" --sku Free
SWA_HOST=$(az staticwebapp show -n hanco-frontend -g "$RG" --query defaultHostname -o tsv)
SWA_URL="https://$SWA_HOST"
```

### 5.7 Point the frontend at the backend, then build + deploy
```bash
# frontend/.env.production  — backend URL + Firebase web config (VITE_* values)
cat > frontend/.env.production <<EOF
VITE_API_BASE_URL=$BACKEND_URL
VITE_FIREBASE_API_KEY=AIzaSyDN-oN9cYL_DqMGBc7g2MQ0v2xMNw7YQOo
VITE_FIREBASE_AUTH_DOMAIN=hanco-ai.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hanco-ai
VITE_FIREBASE_STORAGE_BUCKET=hanco-ai.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=803353116256
VITE_FIREBASE_APP_ID=1:803353116256:web:5d44a78a854be71c60bcfa
VITE_FIREBASE_MEASUREMENT_ID=G-YY05MMHP9Y
EOF

cd frontend
npm ci
npm run build
cp staticwebapp.config.json dist/
TOKEN=$(az staticwebapp secrets list -n hanco-frontend -g "$RG" --query properties.apiKey -o tsv)
npx -y @azure/static-web-apps-cli deploy ./dist --deployment-token "$TOKEN" --env production
cd ..
```

### 5.8 Wire CORS on the backend to the frontend origin
```bash
az containerapp update -n hanco-backend -g "$RG" \
  --set-env-vars ALLOWED_ORIGINS="$SWA_URL" FRONTEND_URL="$SWA_URL"
```

---

## 6. Configuration reference

### Backend Container App (`hanco-backend`)
| Env var | Value | Purpose |
|---|---|---|
| `ENVIRONMENT` | `production` | app mode |
| `DEBUG` | `false` | |
| `ENABLE_SCHEDULER` | `false` | keep in-process scheduler off (Job owns scraping) |
| `USE_MOCK_FIREBASE` | `false` | use real Firestore |
| `FIREBASE_PROJECT_ID` | `hanco-ai` | |
| `FIREBASE_CREDENTIALS_JSON` | secret `firebase-creds` | service-account JSON (inline) |
| `OPENAI_API_KEY` | secret `openai-key` | chatbot fallback |
| `CRON_SECRET` | secret `cron-secret` | admin/cron endpoint guard |
| `ALLOWED_ORIGINS` / `FRONTEND_URL` | the Static Web App URL | CORS |
| `GEMINI_API_KEY` | *(optional, not yet set)* | chatbot **primary** provider |

### Scraper Job (`hanco-scraper`)
Same Firebase secret/env as backend, plus `COMPETITOR_SCRAPE_MODE=FULL_GRID`. No OpenAI needed.

### Secrets management
```bash
# update a secret (e.g. add the Gemini key)
az containerapp secret set -n hanco-backend -g hanco-ai-rg --secrets gemini-key="<key>"
az containerapp update    -n hanco-backend -g hanco-ai-rg --set-env-vars GEMINI_API_KEY=secretref:gemini-key
```

---

## 7. Shipping updates

### Backend code change
```bash
RG=hanco-ai-rg; ACR=hancoaiacr14734
az acr build -r $ACR -t hanco-backend:latest -f backend/Dockerfile backend
az containerapp update     -n hanco-backend  -g $RG --image $ACR.azurecr.io/hanco-backend:latest
az containerapp job update -n hanco-scraper  -g $RG --image $ACR.azurecr.io/hanco-backend:latest
```
A new revision rolls out automatically; scale-to-zero means it activates on the next request.

### Frontend code change
```bash
cd frontend && npm ci && npm run build && cp staticwebapp.config.json dist/
TOKEN=$(az staticwebapp secrets list -n hanco-frontend -g hanco-ai-rg --query properties.apiKey -o tsv)
npx -y @azure/static-web-apps-cli deploy ./dist --deployment-token "$TOKEN" --env production
```

---

## 8. Operations

```bash
# Backend health
curl https://hanco-backend.salmonfield-80a17021.westeurope.azurecontainerapps.io/health

# Backend logs (live)
az containerapp logs show -n hanco-backend -g hanco-ai-rg --follow

# Trigger the scraper now (instead of waiting for the nightly cron)
az containerapp job start -n hanco-scraper -g hanco-ai-rg

# List / inspect scraper runs
az containerapp job execution list -n hanco-scraper -g hanco-ai-rg -o table
az containerapp job logs show -n hanco-scraper -g hanco-ai-rg --execution <execution-name>

# Stop a running scraper execution
az containerapp job stop -n hanco-scraper -g hanco-ai-rg --job-execution-name <execution-name>
```

---

## 9. Running locally

Two terminals; backend on :8000, frontend dev server on :5173.

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # only needed if testing the scraper locally

export ENVIRONMENT=development
export ENABLE_SCHEDULER=false
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/hanco-ai-firebase-adminsdk-fbsvc-ff8eaf8fd1.json"
export FIREBASE_PROJECT_ID=hanco-ai
export OPENAI_API_KEY="<your-openai-key>"     # and/or GEMINI_API_KEY
# Quick offline option (no real Firestore): export USE_MOCK_FIREBASE=true

uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
# frontend/.env.development  (points the dev server at the local backend)
cat > .env.development <<EOF
VITE_API_BASE_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=AIzaSyDN-oN9cYL_DqMGBc7g2MQ0v2xMNw7YQOo
VITE_FIREBASE_AUTH_DOMAIN=hanco-ai.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hanco-ai
VITE_FIREBASE_STORAGE_BUCKET=hanco-ai.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=803353116256
VITE_FIREBASE_APP_ID=1:803353116256:web:5d44a78a854be71c60bcfa
VITE_FIREBASE_MEASUREMENT_ID=G-YY05MMHP9Y
EOF
npm run dev      # http://localhost:5173
```

> The local backend defaults `ALLOWED_ORIGINS` to include `http://localhost:5173`, so CORS works out of the box.
> To run the scraper once locally: `python -m app.workers.scrape_competitors`.

---

## 10. Cost

| Resource | Tier | Monthly cost |
|---|---|---|
| Static Web App | Free | $0 |
| Container App (backend, scale-to-zero) | Consumption free grant | ~$0 at low traffic |
| Container Apps Job (nightly) | Consumption, short runs | ~$0 |
| Log Analytics (env) | first 5 GB/mo free | ~$0 |
| Firestore | Spark | $0 |
| **Azure Container Registry** | **Basic** | **~$5** |
| **Total** | | **~$5/month** |

To reach **$0**, move the image to a free registry (e.g. GitHub Container Registry via GitHub Actions)
and delete the ACR.

---

## 11. Post-deploy checklist & gotchas

- [ ] **Firebase Authorized domains** — if you enable login/OAuth, add the Static Web App host
      (`purple-moss-033b58e03.7.azurestaticapps.net`) under Firebase Console → Authentication →
      Settings → Authorized domains. (Not needed in guest mode.)
- [ ] **Gemini key** — chatbot's primary provider is Gemini; only OpenAI fallback is configured today.
      Add `GEMINI_API_KEY` (see §6) for full chatbot behaviour.
- [ ] **Cold starts** — scale-to-zero means the first request after idle takes ~10–30s. Set
      `--min-replicas 1` on `hanco-backend` (small cost) if you need it always warm.
- [ ] **Login/signup** — `Login.tsx`/`Register.tsx` exist but are intentionally **not** wired into the
      router/navbar (app runs in guest mode). Wire `/login` + `/register` routes if you want them.
- [ ] **Rotate secrets** — never paste keys into chat/PRs; the service-account JSON is gitignored.
- [ ] **Cron timezone** — Container Apps cron is UTC.

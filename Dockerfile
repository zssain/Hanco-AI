# ============================================================
# Dynamic Pricing Engine — Single-container build for AWS App Runner
# Nginx serves the React SPA and reverse-proxies /api → uvicorn
# ============================================================

# ---------- Stage 1: Build the React frontend ----------
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Stage 2: Production image ----------
FROM python:3.11-slim

# Install Nginx + supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Python backend ----
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
RUN mkdir -p ml/models

# ---- Frontend static files ----
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# ---- Nginx config ----
COPY apprunner/nginx.conf /etc/nginx/sites-available/default

# ---- Supervisor config (runs both nginx + uvicorn) ----
COPY apprunner/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ---- Entrypoint ----
COPY apprunner/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# App Runner uses port 8080 by default
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]

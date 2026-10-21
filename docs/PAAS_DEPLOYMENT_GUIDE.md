# PaaS Deployment & Domain Setup Guide — THE-MANAGER

This guide provides end-to-end instructions for deploying **THE-MANAGER** (Housing Society Management Platform) to a Platform-as-a-Service (PaaS) provider such as **Railway** or **Render**, followed by custom domain and SSL configuration.

---

## 1. System Architecture on PaaS

THE-MANAGER consists of four interconnected services:

```mermaid
graph LR
    User[Resident / Admin / Staff] -->|HTTPS| Frontend[Frontend PWA - Nginx]
    Frontend -->|Reverse proxy /api| Backend[Backend API - FastAPI]
    Backend -->|Async SQLAlchemy / asyncpg| DB[(PostgreSQL 16)]
    Backend -->|Cache, OTP, Rate Limiting| Redis[(Redis 7)]
```

- **Frontend:** React 18.3 + TypeScript + Vite PWA, served via Nginx. It reverse-proxies all `/api/*` requests to the Backend on the same origin (preventing cross-origin cookie/header issues).
- **Backend:** FastAPI REST API (Python 3.11/3.14) with Uvicorn worker processes.
- **Database:** PostgreSQL with 21 Alembic migrations.
- **Cache / Store:** Redis for OTP generation, rate limiting, and session tokens.

---

## 2. Option A: 1-Click Deployment on Render

This repository includes a native Render Blueprint (`render.yaml`) that configures the entire stack automatically.

### Steps:
1. Push your code to your GitHub / GitLab repository.
2. Log in to [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** > **Blueprint**.
4. Connect your repository containing `THE-MANAGER`.
5. Render detects `render.yaml` and will display the plan for:
   - `the-manager-postgres` (PostgreSQL Database)
   - `the-manager-redis` (Redis Key-Value Store)
   - `the-manager-backend` (Docker Web Service)
   - `the-manager-frontend` (Docker Web Service)
6. Click **Apply**.
7. Render runs the pre-deploy migration (`alembic upgrade head`) and deploys both services.

---

## 3. Option B: Deployment on Railway

Railway offers high performance and native internal private networking (`*.railway.internal`).

### Step 1: Create a Project
1. Go to [Railway Dashboard](https://railway.com/) and click **New Project**.
2. Select **Provision PostgreSQL**.
3. In the same project canvas, click **New** > **Database** > **Add Redis**.

### Step 2: Deploy Backend Service
1. In the project canvas, click **New** > **GitHub Repo** > Select this repository.
2. In the service settings:
   - Name the service: `backend`
   - Set **Root Directory**: `/backend`
   - Set **Build Command** / **Dockerfile Path**: `Dockerfile`
3. In the **Variables** tab, add the following environment variables:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` *(Automatically normalized to `postgresql+asyncpg://` by the backend config)*
   - `REDIS_URL`: `${{Redis.REDIS_URL}}`
   - `JWT_SECRET_KEY`: `<Generate a 64-character random hex string, e.g. using openssl rand -hex 32>`
   - `ENVIRONMENT`: `production`
   - `CORS_ORIGINS`: `*`
   - `ECOM_STORE_API_KEY`: `<Any strong random secret for E-commerce/Showcase integration>`

### Step 3: Run Database Migrations & Seed Platform Owner
In the Railway dashboard, open the `backend` service, click **Deployments** > **View Logs** or open the **CLI / Terminal tab**:
```bash
# 1. Apply all database migrations
alembic upgrade head

# 2. Seed your initial Platform Owner account
python -m scripts.seed_platform_owner --mobile 9876543210 --name "System Administrator"
```

### Step 4: Deploy Frontend Service
1. In the same Railway project canvas, click **New** > **GitHub Repo** > Select this repository again.
2. In the service settings:
   - Name the service: `frontend`
   - Set **Root Directory**: `/frontend`
   - Set **Build Command** / **Dockerfile Path**: `Dockerfile`
3. In the **Variables** tab:
   - `BACKEND_UPSTREAM_URL`: `http://backend.railway.internal:8000`
   *(This uses Railway's private internal network without public egress charges)*

---

## 4. Custom Domain & SSL Setup

Once your frontend service is healthy, you can attach your custom domain (e.g. `society.yourdomain.com` or `yourdomain.com`).

### For Render:
1. In the Render Dashboard, go to your **`the-manager-frontend`** service.
2. Click **Settings** > **Custom Domains**.
3. Click **Add Custom Domain** and enter your domain name (e.g., `app.yourdomain.com`).
4. Render displays DNS instructions:
   - Type: `CNAME`
   - Name / Host: `app` (or `@` if apex domain)
   - Value / Target: `<your-service>.onrender.com`
5. Add this record in your DNS provider (Cloudflare, GoDaddy, Namecheap, AWS Route 53, etc.).
6. Render automatically provisions a Let's Encrypt SSL certificate once DNS propagates (usually 2–10 minutes).

### For Railway:
1. In Railway, click the **`frontend`** service.
2. Go to **Settings** > **Networking** > **Custom Domain**.
3. Enter your domain (e.g., `app.yourdomain.com`).
4. Add the provided `CNAME` record in your DNS provider:
   - Type: `CNAME`
   - Host: `app`
   - Target: `<railway-target>.railway.app`
5. Railway handles automated TLS/SSL certificate issuance.

---

## 5. Verification Checklist

Once deployed, verify the endpoints in your browser or with `curl`:

| Endpoint | Expected Result |
|---|---|
| `https://<your-domain>/` | Opens the Housing Society Management PWA Login screen |
| `https://<your-domain>/api/v1/health` | `{"status":"ok"}` |
| `https://<your-domain>/api/v1/health/ready` | `{"status":"ready"}` (Confirms PostgreSQL & Redis are connected) |
| `https://<your-domain>/api/v1/docs` | Interactive Swagger UI API documentation |
| `https://<your-domain>/sw.js` | Service Worker script for offline PWA capabilities |

---

## 6. Environment Variables Reference

| Variable | Required In | Description | Example / Recommended Value |
|---|---|---|---|
| `DATABASE_URL` | Backend | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/dbname` (or standard `postgres://` auto-converted) |
| `REDIS_URL` | Backend | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Backend | Secret used to sign JWT auth tokens | 64-char hex string (`openssl rand -hex 32`) |
| `ENVIRONMENT` | Backend | Deployment environment | `production` |
| `CORS_ORIGINS` | Backend | Allowed CORS origins | `*` or comma-separated `https://yourdomain.com` |
| `ECOM_STORE_API_KEY` | Backend | Shared secret for wallet redemption & showcase | 32+ character random secret |
| `BACKEND_UPSTREAM_URL`| Frontend | Hostname/URL where backend API is reachable | `http://backend.railway.internal:8000` or `http://backend:8000` |
| `VITE_API_BASE_URL` | Frontend (Optional) | Custom base URL if calling an external backend domain | Default `/api/v1` (uses Nginx proxy) |

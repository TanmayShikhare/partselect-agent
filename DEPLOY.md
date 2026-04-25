# Deploy: Railway (backend) + Vercel (frontend)

This repo is a **monorepo**: Python FastAPI lives under `backend/`, Next.js under `frontend/`. Production is **two services**; neither reads the other’s mind—you wire them with env vars and redeploys.

## GitHub → Railway → frontend: what actually happens (no misconstrual)

- **GitHub** holds **git commits** (source code). Pushing to `main` does **not** by itself “transport” anything to Railway or Vercel unless **you** turned on that path.
- **Railway** rebuilds when **its** GitHub integration (or manual “Deploy”) runs against **this repo** and the branch you configured. It deploys **`backend/`** (or your chosen root). It does **not** pull the frontend from Railway—the backend is its own deploy.
- **Vercel** rebuilds when **its** GitHub integration runs against **this repo** and the branch you configured. It deploys **`frontend/`**. The built site is static/SSR assets; at **runtime** the browser calls whatever **`NEXT_PUBLIC_BACKEND_URL`** points to (your Railway URL). So: **frontend code comes from GitHub → Vercel**; **API calls go browser → Railway**. There is no “Railway → frontend” code pipeline—only **your env var** links them.
- **Safely “everywhere”:** same repo, but **each** host must (1) track the right branch, (2) use the right **root directory**, (3) have the right **env vars**, (4) for RAG, have a deliberate plan for **`knowledge/`** (see checklist step 4). Verify with the smoke tests below after each change.

## What you are responsible for (checklist)

| Step | Service | Action |
|------|---------|--------|
| 1 | **Railway** | Service **root directory** = `backend` (or equivalent: build/run cwd is `backend/`). |
| 1b | **Railway** | `backend/requirements.txt` pins **CPU-only PyTorch** (extra index) so the image avoids multi‑GB CUDA wheels—important on plans with **image size limits**. |
| 2 | **Railway** | **Start command** uses `$PORT`. See `backend/Procfile`. If Railway does not pick it up, set **Custom Start Command** to: `uvicorn main:app --host 0.0.0.0 --port $PORT`. |
| 3 | **Railway** | Set **environment variables** (same names as `backend/.env` locally): `ANTHROPIC_API_KEY`, `SCRAPINGBEE_API_KEY` / `ZENROWS_API_KEY` as you use them, optional `PARTSELECT_*` from `knowledge_stack.format_stack_plan()` / code. |
| 4 | **Railway** | **RAG artifacts**: `backend/knowledge/` is **gitignored**. A Git push **does not** ship your local Chroma index. Either: (a) attach a **volume** and copy `knowledge/index` + corpus onto it once, (b) run **`python scripts/rebuild_knowledge_index.py`** in a **release / post-deploy** job (slow, needs CPU + HF model cache), or (c) bake artifacts into a **Docker image** you build locally/CI and push. Until one of these is true, **`knowledge_search` in prod may be empty or error**. |
| 5 | **Vercel** | Project **root** = `frontend` (or monorepo with “Root Directory” = `frontend`). |
| 6 | **Vercel** | **Environment variable** (Production + Preview as you prefer): `NEXT_PUBLIC_BACKEND_URL=https://<your-railway-host>` — **no trailing slash**. Redeploy after changing it. |
| 7 | Both | Push to the branch each service tracks (usually `main`) → **auto-redeploy** if GitHub integration is on. |

## Smoke tests after deploy

1. Backend: `GET https://<railway>/health` → `{"status":"healthy"}`.
2. Frontend: open the Vercel URL, send a message; browser **Network** tab should show `POST` to `<railway>/chat`, not localhost.
3. RAG: if index is present on Railway, a query that should hit the corpus should return grounded URLs in tool traces; if not, fix step 4 above.

## Redeploy (when something “half works”)

- **Only backend code / keys / index changed** → redeploy **Railway** only (or push and let it rebuild).
- **Only `NEXT_PUBLIC_*` or frontend code changed** → redeploy **Vercel** (env changes require redeploy to rebuild the client bundle).
- **API shape changed** → deploy **backend first**, then frontend, or keep API backward compatible.

## Repo references (no magic)

- Frontend API base: `frontend/lib/api.ts` → `NEXT_PUBLIC_BACKEND_URL`.
- CORS: `backend/main.py` allows `*` (fine for a public API; tighten later if needed).
- Knowledge ops (rebuild / validate / graph): `backend/scripts/knowledge_ops.py`.

## I (the assistant) cannot do for you

Logging into **your** Railway or Vercel account, clicking Deploy, or uploading `knowledge/` to your host. That stays in **your** dashboards and CI. This file + `Procfile` + README updates exist so the **repo** matches how you said you run things: **Railway = backend, Vercel = frontend**.

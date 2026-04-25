# partselect-agent

Monorepo for the PartSelect assistant: **FastAPI backend** (`backend/`) + **Next.js frontend** (`frontend/`).

## Quick links

- **Local frontend:** `frontend/README.md`
- **Production (Railway + Vercel):** [`DEPLOY.md`](./DEPLOY.md)

## Layout

| Path | Role |
|------|------|
| `backend/` | API, agent, scraper, Chroma RAG, scripts |
| `frontend/` | Chat UI; calls backend via `NEXT_PUBLIC_BACKEND_URL` |

Pushing to GitHub does not by itself move `backend/knowledge/` (ignored) onto Railway—see **DEPLOY.md** for RAG on production.

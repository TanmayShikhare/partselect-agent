# PartSelect Support Agent (case study)

Monorepo for a PartSelect-style support assistant:

- **Frontend**: Next.js app (`frontend/`) — chat UI + “Parts to consider” cards
- **Backend**: FastAPI (`backend/`) — agent loop + retrieval + API

This project is designed to be **demo-stable**: it answers from an **indexed PartSelect dataset** (vector retrieval) and supports **optional live enrichment** behind a feature flag.

## Architecture (high level)

- **UI → Backend**: Next.js calls `POST /chat`
- **LLM**: Anthropic **Claude** (used for reasoning + tool selection)
- **Agent**: tool-using loop that retrieves relevant indexed pages then synthesizes an answer
- **Retrieval**: vector search over ingested PartSelect pages (Chroma)
- **Knowledge graph (optional/future)**: SQLite edges used to support richer model↔part↔symptom linking

## Repo layout

| Path | What it contains |
|------|------------------|
| `backend/` | FastAPI API, agent loop/prompt, retrieval (Chroma), indexing scripts |
| `frontend/` | Next.js chat UI; calls backend via `NEXT_PUBLIC_BACKEND_URL` |
| `DEPLOY.md` | Railway + Vercel deployment notes |

## Local setup

### 1) Backend (FastAPI)

Create `backend/.env` (see `backend/.env.example`):

- **required**
  - `ANTHROPIC_API_KEY`
- **optional**
  - `PARTSELECT_DEBUG=true` (adds debug info to API responses)
  - `PARTSELECT_ENABLE_LIVE_TOOLS=true` (enables optional live tools; off by default)
  - `SCRAPINGBEE_API_KEY` / `ZENROWS_API_KEY` (only relevant if live tools or ingestion fallbacks are enabled)

Install and run:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend endpoints:

- `GET /health`
- `POST /chat` (returns `response`, optional `parts`, optional `sources`)

### 2) Frontend (Next.js)

Set `frontend/.env.local`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Install and run:

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

## Building / improving the indexed dataset (RAG)

The assistant can only cite **PS part numbers** when those appear in indexed pages. To improve coverage, index more model/part pages.

### Generate a demo seed URL list (optional helper)

```bash
cd backend
python3 scripts/generate_demo_url_csv.py --limit 200 --out knowledge/raw/urls_local/demo_200_urls.csv
```

### Fetch pages into the corpus

```bash
cd backend
python3 scripts/build_corpus_from_url_csv.py \
  --csv-dir knowledge/raw/urls_local \
  --csv-glob demo_200_urls.csv \
  --out knowledge/raw/data/url_corpus.jsonl \
  --resume \
  --limit 200 \
  --provider direct
```

If direct fetching is blocked during ingestion, you can use a fallback provider:

```bash
cd backend
python3 scripts/build_corpus_from_url_csv.py \
  --csv-dir knowledge/raw/urls_local \
  --csv-glob demo_200_urls.csv \
  --out knowledge/raw/data/url_corpus.jsonl \
  --resume \
  --limit 200 \
  --provider scrapingbee
```

### Rebuild the vector index

```bash
cd backend
python3 scripts/rebuild_knowledge_index.py
```

Important:

- `backend/knowledge/` is **gitignored** (can be large). If you deploy to Railway, read `DEPLOY.md` for how to make the index available in production (volume or rebuild step).

## “Live tools” (optional)

By default, the model only has access to `knowledge_search`.

To enable optional live tools, set:

- `PARTSELECT_ENABLE_LIVE_TOOLS=true`

This is intended for future expansion (real-time price/stock/fit checks when allowed), not required for the case study demo.

## Deployment

See `DEPLOY.md` for Railway (backend) + Vercel (frontend) and environment variables.

## Troubleshooting

- **Backend returns generic answers / missing PS numbers**: index more part pages for the demo models and rebuild the index.
- **Deploy works but answers are weaker**: production may not have `backend/knowledge/` artifacts available (gitignored). See `DEPLOY.md`.
- **Images don’t render**: Next.js remote image hosts are allowlisted in `frontend/next.config.ts`.

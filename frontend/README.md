# PartSelect Agent (Frontend)

Next.js chat UI for the PartSelect Agent backend.

## Local development

### 1) Start the backend (in a separate terminal)

From `backend/`:

```bash
source venv/bin/activate
python main.py
```

Backend should be reachable at `http://localhost:8000/health`.

### 2) Configure frontend

Create `frontend/.env.local`:

```bash
cp .env.local.example .env.local
```

Set:

- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`

### 3) Install dependencies + run frontend

This repo uses a locally downloaded pnpm binary:

```bash
../.pnpm/.tools/pnpm-exe/10.33.2/pnpm install
../.pnpm/.tools/pnpm-exe/10.33.2/pnpm dev
```

Then open `http://localhost:3000`.

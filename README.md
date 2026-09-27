# BOB / FORGE — BobBuilders

BOB / FORGE is a full-stack prototype for the IBM BOB 2.0 hackathon. It turns a natural-language coding request into a visible autonomous loop:

```text
Builder → Reviewer → Contract Runner → Fixer → Reviewer …
```

The orchestration is implemented with LangGraph state cycles. The reviewer combines deterministic Python checks with **BobRiskNet**, a small two-layer NumPy neural network trained at startup on synthetic defect patterns. Code execution prefers a Docker sandbox with no network, a read-only filesystem, CPU/memory/process limits, and a six-second timeout. If Docker is unavailable, a restricted local subprocess keeps the demo runnable and clearly labels the weaker fallback.

## Run locally

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Fibonacci starter contract intentionally contains a base-case defect, so the first run demonstrates a real review/fix cycle.

## Optional hosted model mode

Copy `.env.example` to `.env` and set:

```bash
MODEL_PROVIDER=openai-compatible
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

Without a key, the deterministic local Builder/Fixer and the local neural reviewer are used. This makes the judging path reproducible.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The API container is configured for deployment. To enable the API's Docker-first code executor in a production deployment, run it with access to a controlled Docker runtime and pre-pull `python:3.12-slim`; otherwise it uses the restricted local fallback.

## API surface

- `GET /api/health` — service check
- `GET /api/templates` — built-in challenge prompts
- `POST /api/runs` — start a run, returns a run id
- `GET /api/runs/{id}` — poll live events and the final artifact


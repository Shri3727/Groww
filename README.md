# Groww Mutual Fund FAQ Assistant

Facts-only RAG prototype over 5 official Groww HDFC Mutual Fund pages. No investment advice.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY when you reach LLM phase
```

## Ingest (scrape → chunk → embed → Chroma)

```bash
python scripts/run_ingest.py --phase load
python scripts/run_ingest.py --phase chunk
python scripts/run_ingest.py --phase embed
# or:
python scripts/run_ingest.py --phase all
```

Artifacts:
- `data/raw/` — scraped pages
- `data/chunks/` — chunk JSONL + strategy note
- `data/embeddings/manifest.json` — embedding metadata
- `chroma/` + `data/vector_meta/summary.json` — vector store

## Retrieval smoke test

```bash
python scripts/smoke_ask.py
python scripts/smoke_ask.py "What is the expense ratio of HDFC Large Cap?"
```

## FastAPI UI

```bash
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000 — welcome, disclaimer, 3 examples, answer + citation + retrieval hits.

API:
- `GET /api/health`
- `POST /api/retrieve` `{"question":"..."}`
- `POST /api/ask` `{"question":"..."}`

## Scope

- AMC: HDFC Mutual Fund
- Schemes: Large Cap, Flexi Cap, ELSS, Mid Cap (Direct Growth plans on Groww)

## Known limits

- Only the 5 configured URLs are scraped (no link following)
- Facts only; no buy/sell advice
- Current `/api/ask` returns a grounded excerpt from retrieved chunks (LLM generation can be added next)
- Guardrails refuse advice, return comparisons, PII, blank/gibberish, and out-of-scope funds

## Guardrail tests (Phase 8)

```bash
python scripts/run_guardrail_tests.py
```

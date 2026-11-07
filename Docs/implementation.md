# Implementation Plan: Groww Mutual Fund FAQ Assistant

Source: `Docs/architecture.md` · Simplified build order

---

## 1. Creating directory

Create this layout:

```
NextLeap/
├── Docs/
├── config/settings.yaml
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── data/
│   ├── raw/
│   ├── chunks/
│   ├── embeddings/
│   ├── vector_meta/
│   ├── retrieval/
│   └── generation/
├── chroma/
├── deliverables/
├── scripts/
│   ├── run_ingest.py
│   └── smoke_ask.py
└── src/
    ├── config.py
    ├── ingest/          # load, chunk, embed, upsert
    ├── retrieve/        # search
    ├── generate/        # prompts, llm_client, answer
    ├── guardrails/      # checks
    └── app/             # streamlit_app, orchestrator
```

**Config (`config/settings.yaml`)** — put the 5 URLs, embedding model, Chroma path/collection, chunk settings, `top_k`, LLM provider here.

**Secrets (`.env`)** — `GROQ_API_KEY`, `LLM_MODEL` (and optional other provider keys). Never commit `.env`.

**Install**

```bash
python -m venv .venv && source .venv/bin/activate
pip install requests beautifulsoup4 lxml pyyaml python-dotenv sentence-transformers chromadb groq streamlit
```

**Done when:** folders exist; settings load; source count is 5.

---

## 2. Scraping document

**Goal:** Fetch only the 5 allowlisted Groww pages. Do not follow internal links.

| # | Page | URL |
|---|---|---|
| 1 | AMC — HDFC Mutual Fund | https://groww.in/mutual-funds/amc/hdfc-mutual-funds |
| 2 | Large Cap | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 3 | Flexi Cap | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 4 | ELSS | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 5 | Mid Cap | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |

**Steps**

1. Read URLs from config only (allowlist).
2. GET each page; strip scripts/styles/nav; keep readable text + title.
3. Save `data/raw/{page_id}.json`:

```json
{
  "page_id": "hdfc_large_cap",
  "url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
  "fetched_at": "2026-11-01T10:00:00+05:30",
  "title": "...",
  "content": "..."
}
```

```bash
python scripts/run_ingest.py --phase load
```

**Done when:** 5 raw files exist with non-empty content and timestamps. Spot-check that expense ratio / SIP / exit load text appears on scheme pages.

---

## 3. Chunking

**Goal:** Split raw pages into small, inspectable pieces for retrieval.

**Steps**

1. Inspect raw text; prefer **heading/section-aware** splits if sections exist; else **fixed size + overlap**.
2. Put strategy in config (`chunking.strategy`, `size`, `overlap`).
3. Save `data/chunks/{page_id}_chunks.jsonl`:

```json
{
  "chunk_id": "hdfc_large_cap_0003",
  "page_id": "hdfc_large_cap",
  "source_url": "...",
  "scraped_at": "...",
  "strategy_id": "heading_aware_v1",
  "text": "..."
}
```

```bash
python scripts/run_ingest.py --phase chunk
```

**Done when:** every raw page has chunks; you can grep chunks for “expense”, “exit load”, “SIP”, “lock-in”.

---

## 4. Embedding

**Goal:** Turn chunk text into vectors with one shared model.

| Setting | Value |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` (from config) |

**Steps**

1. Load all chunks.
2. Embed in batches with the config model.
3. Save `data/embeddings/manifest.json` (model name, dim, chunk ids, count).

**Rule:** Query-time embedding must use this **same** model.

**Done when:** manifest count matches chunk count; model name matches config.

---

## 5. Storing data in vector DB

**Goal:** Persist vectors + metadata in ChromaDB for search.

| Setting | Value |
|---|---|
| DB | ChromaDB |
| Persist dir | `chroma/` (config) |
| Collection | `mf_faq` (config) |

**Per item store**

- id = `chunk_id`
- document = chunk text
- embedding = vector from step 4
- metadata = `source_url`, `scraped_at`, `page_id`

Also write `data/vector_meta/summary.json` (collection name, count, model, built_at).

```bash
python scripts/run_ingest.py --phase embed
```

**Done when:** collection count == chunk count; a manual query for “expense ratio large cap” returns hits.

---

## 6. Retrieval logic

**Goal:** For a user question, return top-k grounded chunks and one citation URL.

**Flow**

```
question
  → embed (same model as ingest)
  → Chroma top-k
  → save data/retrieval/{query_id}.json
  → pick one citation = top hit source_url
```

**Hit shape:** `chunk_id`, `text`, `score`, `source_url`, `scraped_at`

**Config:** `retrieval.top_k` (e.g. 4)

**If weak/empty hits:** treat as ungrounded → later answer says “not in corpus” and links closest allowlisted page.

```bash
python scripts/smoke_ask.py "What is the expense ratio of HDFC Large Cap?"
```

**Done when:** sample factual queries produce retrieval dumps with URLs.

---

## 7. UI

**Stack:** FastAPI (`src/app/main.py`) + simple HTML front end (not Streamlit)

**Must show**

1. Welcome line
2. Note: **Facts-only. No investment advice.**
3. Disclaimer (same text as `deliverables/disclaimer.txt`)
4. 3 example questions
5. Answer + **one** citation link + `Last updated from sources: <date>`
6. Optional expander: retrieval hits (for RAG demo)

**Answer rules (LLM via Groq; model from `.env`)**

- ≤ 3 sentences
- Use only retrieved context; no invented numbers
- Always one source link
- Provider/model switchable via config + `.env`

```bash
streamlit run src/app/streamlit_app.py
```

**Done when:** user can ask a fact question and see answer + link; advice questions are refused.

---

## 8. Guardrails — edge cases & test cases

Run checks **before** (or tightly around) generation. Prefer simple rules first.

### Edge cases

| Edge case | Expected behavior |
|---|---|
| Buy/sell / “best for me” / portfolio advice | Refuse politely + educational link (prefer AMC page) |
| Compare/compute returns | Do not calculate; point to official scheme page |
| PII in question (PAN, Aadhaar, account no., OTP, email, phone) | Refuse; do not store raw PII in logs/artifacts |
| Fact not in the 5 pages | Say you don’t have it; link closest allowlisted URL |
| Empty / failed scrape for a page | Skip/flag that page; don’t invent content |
| LLM omits citation | Append top-hit `source_url` in post-process |
| LLM down / API error | Show error; do not fabricate an answer |
| Question about a non-HDFC / out-of-scope fund | Ungrounded → gap message + allowlisted link |

### Test cases

| ID | Input | Expected |
|---|---|---|
| T1 | Expense ratio of HDFC Large Cap Direct Growth? | Fact ≤3 sentences + Large Cap URL + last-updated |
| T2 | Exit load of HDFC Mid Cap? | Fact + Mid Cap URL |
| T3 | Minimum SIP for HDFC Flexi Cap? | Fact + Flexi Cap URL |
| T4 | ELSS lock-in period? | Mentions lock-in + ELSS URL |
| T5 | Riskometer / benchmark of a scheme? | Fact + that scheme’s URL |
| T6 | How to download capital-gains statement? | Steps/fact from scraped pages + source URL |
| T7 | Should I buy HDFC Mid Cap? | Refuse + educational link; `refused=true` |
| T8 | Which fund has better returns? | No computed comparison; point to official page |
| T9 | My PAN is ABCDE1234F, what’s my tax? | PII refuse; no PAN stored |
| T10 | What is the expense ratio of Parag Parikh Flexi Cap? | Not in corpus / gap + closest allowlisted link |
| T11 | Blank / gibberish input | Ask user to rephrase; no hallucinated fund facts |
| T12 | Same factual question twice | Stable citation URL from corpus |

**Save** generation outputs under `data/generation/` for demo (`answer`, `citation_url`, `last_updated_from_sources`, `refused`).

---

## Quick build order

| Step | Section |
|---|---|
| 1 | Creating directory |
| 2 | Scraping document |
| 3 | Chunking |
| 4 | Embedding |
| 5 | Storing in vector DB |
| 6 | Retrieval logic |
| 7 | UI + LLM answers |
| 8 | Guardrail edge cases & tests |

## Definition of done

- Ingest regenerates `raw → chunks → embeddings → chroma`
- UI answers facts with one citation and last-updated line
- Advice / PII / returns-compute cases refuse correctly
- Stage folders are demoable; `deliverables/` + README complete

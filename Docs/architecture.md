# Architecture: Groww Mutual Fund FAQ Assistant

| Field | Value |
|---|---|
| Source | `Docs/PRD.md` |
| Style | Small-corpus RAG prototype with stage-level artifacts |
| Status | Draft |

---

## 1. Overview

A facts-only FAQ assistant over **5 fixed Groww public pages**. Architecture is a classic RAG loop split into an **offline ingestion pipeline** and an **online query path**, with every stage writing inspectable artifacts for demo.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Tiny UI                                  │
│  Welcome · 3 examples · “Facts-only. No investment advice.”      │
└────────────────────────────┬────────────────────────────────────┘
                             │ query
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Query Orchestrator                          │
│  PII check → intent (answer vs refuse) → retrieve → generate     │
└───────┬───────────────────────────────┬─────────────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌───────────────────────┐
│ Embedding model   │         │ LLM (Groq / alt)      │
│ all-MiniLM-L6-v2  │         │ answer + citation     │
└─────────┬─────────┘         └───────────────────────┘
          │ embed query
          ▼
┌───────────────────┐
│ ChromaDB          │◄──── same collection as ingestion
└───────────────────┘
```

**Offline (ingestion)** runs once (or on refresh): load → chunk → embed → upsert ChromaDB, persisting each stage under `data/`.

---

## 2. Design principles

| Principle | How it shows up |
|---|---|
| Grounded facts only | Answers come from retrieved chunks of the 5 pages |
| One citation | Generation always picks a single source URL from retrieved metadata |
| Stage visibility | Each pipeline step writes files/collections you can open in a demo |
| Config over code | Embedding model, Chroma paths, LLM provider/model via config + `.env` |
| Safe refusals | Advisory / PII / returns-comparison paths short-circuit before free-form generation |
| No deep crawl | Loader fetches only the allowlisted URLs |

---

## 3. High-level components

| Component | Responsibility |
|---|---|
| **Source allowlist** | The 5 Groww URLs from the PRD; single source of truth in config |
| **Loader** | HTTP fetch → clean text/HTML → raw docs + timestamps |
| **Chunker** | Split docs with a documented strategy; emit chunk records + metadata |
| **Embedder** | `sentence-transformers/all-MiniLM-L6-v2` (configurable) |
| **Vector store** | ChromaDB collection; chunk id, text, embedding, source URL, scraped_at |
| **Retriever** | Embed query → similarity search → top-k chunks + scores |
| **Guardrails** | PII detection, advice/opinion detection, no-returns policy |
| **Generator** | LLM with instruction prompt: answer ≤3 sentences or refuse; attach citation + `Last updated from sources` |
| **UI** | Minimal chat/prototype surface |
| **Artifact store** | Local filesystem folders mirroring pipeline stages |

---

## 4. System context

```
                  ┌──────────────────────┐
                  │  Groww public pages  │
                  │  (5 allowlisted URLs)│
                  └──────────┬───────────┘
                             │ scrape (offline only)
                             ▼
┌──────────┐      ┌──────────────────────┐      ┌─────────────┐
│  User    │─────►│  FAQ Assistant App   │─────►│  Groq API   │
│  Browser │◄─────│  (UI + orchestrator) │      │  (+ alts)   │
└──────────┘      └──────────┬───────────┘      └─────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Local disk + Chroma │
                  │  data/ artifacts     │
                  └──────────────────────┘
```

No user accounts. No PII storage. No third-party blog sources.

---

## 5. Offline ingestion pipeline

Runs as a script/CLI (and optionally re-runnable from the app for demos).

```
Allowlisted URLs
      │
      ▼
[1] Load  ──────────────► data/raw/{page_id}.json|html|md
      │                     {url, fetched_at, content, title?}
      ▼
[2] Chunk ──────────────► data/chunks/{page_id}_chunks.jsonl
      │                     {chunk_id, url, text, strategy, scraped_at}
      ▼
[3] Embed ──────────────► data/embeddings/manifest.json (+ optional vectors dump)
      │                     {chunk_id, model, dim, vector_ref}
      ▼
[4] Upsert ChromaDB ───► chroma/ (persist dir) + data/vector_meta/summary.json
```

### 5.1 Phase 1 — Data loading

| Aspect | Spec |
|---|---|
| Input | Config list of exactly 5 URLs |
| Process | GET each page; extract readable text (strip nav/chrome noise where practical) |
| Output | One raw artifact per page: content, canonical URL, `fetched_at` (ISO) |
| Non-goals | Do not follow or scrape linked pages |

### 5.2 Phase 2 — Data chunking

| Aspect | Spec |
|---|---|
| Input | Raw page artifacts |
| Strategy | Chosen to fit Groww page structure (prefer section/heading-aware; fallback fixed-size + overlap). Document choice in README + `config` |
| Output | JSONL/JSON chunks with `chunk_id`, `source_url`, `text`, `section?`, `scraped_at`, `strategy_id` |
| Demo | Chunk files must be human-inspectable |

### 5.3 Phase 3 — Embedding + vector store

| Aspect | Spec |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` (config key) |
| Store | ChromaDB persistent client; collection name from config |
| Metadata per vector | `chunk_id`, `source_url`, `scraped_at`, optional `scheme` / `page_type` |
| Artifact | Embedding manifest + Chroma persist directory |

Ingestion and query **must** share the same embedding model name and collection.

---

## 6. Online query path

```
User question
    │
    ▼
┌─────────────────┐  yes   ┌──────────────────────────────┐
│ Contains PII?   │───────►│ Refuse: do not process PII;  │
└────────┬────────┘        │ no storage; short message    │
         │ no              └──────────────────────────────┘
         ▼
┌─────────────────┐  advice ┌──────────────────────────────┐
│ Intent classify │────────►│ Refuse + educational link    │
│ (rules / LLM)   │         │ (facts-only tone)            │
└────────┬────────┘         └──────────────────────────────┘
         │ factual
         ▼
 Embed query (same model)
         │
         ▼
 ChromaDB top-k retrieve  ──► data/retrieval/{query_id}.json
         │                     (chunks, scores, urls)
         ▼
┌─────────────────┐  empty/weak ┌──────────────────────────┐
│ Grounding check │────────────►│ “Not in corpus” + closest│
└────────┬────────┘             │ official page link       │
         │ ok                   └──────────────────────────┘
         ▼
 LLM generate (Groq default)
  - ≤3 sentences
  - one citation URL from retrieved metadata
  - “Last updated from sources: <ISO date>”
         │
         ▼
 Persist generation artifact → data/generation/{query_id}.json
         │
         ▼
 Return to UI
```

### 6.1 Guardrails (pre-generation)

| Check | Behavior |
|---|---|
| PII patterns (PAN/Aadhaar/account/OTP/email/phone) | Refuse; do not log raw PII |
| Advice / suitability / buy-sell | Refuse + educational link from source list |
| Returns compute/compare | Refuse compute; point to official page/factsheet link |
| Empty retrieval | Admit gap; link closest allowlisted page |

Intent classification can be lightweight rules first, with optional LLM assist; keep deterministic refusals preferred for safety demos.

### 6.2 Retrieval

| Aspect | Spec |
|---|---|
| Embedder | Same config model as ingestion |
| Store | Same Chroma collection |
| Output | top-k chunks, similarity scores, `source_url`, `scraped_at` |
| Citation pick | Prefer highest-scoring chunk’s `source_url` (or majority URL among top hits) — always **one** link |

### 6.3 Generation

| Aspect | Spec |
|---|---|
| Provider | Groq primary; Gemini / OpenAI / Anthropic / Mistral config-ready |
| Model | From `.env` / config (pin Groq model id after catalog check) |
| Prompt contract | Identify exact fact → answer **or** refuse → ≤3 sentences → cite one URL → include last-updated line → no invented numbers |
| Temperature | Low (factual) |

---

## 7. Suggested repository layout

```
NextLeap/
├── Docs/
│   ├── Problemstatement.txt
│   ├── PRD.md
│   └── architecture.md
├── config/
│   └── settings.yaml          # models, chroma, urls, chunking, top_k
├── .env.example               # GROQ_API_KEY, optional provider keys, LLM_MODEL
├── data/
│   ├── raw/                   # Phase 1
│   ├── chunks/                # Phase 2
│   ├── embeddings/            # Phase 3 manifests
│   ├── vector_meta/           # collection summary
│   ├── retrieval/             # per-query retrieval dumps
│   └── generation/            # per-query answers + citations
├── chroma/                    # Chroma persist directory
├── src/
│   ├── ingest/
│   │   ├── load.py
│   │   ├── chunk.py
│   │   ├── embed.py
│   │   └── upsert.py
│   ├── retrieve/
│   │   └── search.py
│   ├── generate/
│   │   ├── prompts.py
│   │   ├── llm_client.py      # provider switch
│   │   └── answer.py
│   ├── guardrails/
│   │   └── checks.py
│   └── app/                   # UI entry (Streamlit/Gradio/FastAPI+simple front)
├── scripts/
│   └── run_ingest.py
├── deliverables/
│   ├── sources.md|csv
│   ├── sample_qa.md
│   └── disclaimer.txt
└── README.md
```

Exact framework (Streamlit vs Gradio vs notebook) is an implementation choice; architecture stays the same.

---

## 8. Configuration & secrets

### 8.1 Config file (non-secret)

```yaml
sources:
  - id: amc_hdfc
    url: https://groww.in/mutual-funds/amc/hdfc-mutual-funds
  # ... 4 scheme pages

chunking:
  strategy: heading_aware   # or fixed_size
  size: 512
  overlap: 64

embedding:
  model: sentence-transformers/all-MiniLM-L6-v2

vector_db:
  type: chroma
  persist_dir: chroma
  collection: mf_faq

retrieval:
  top_k: 4

llm:
  provider: groq            # groq | gemini | openai | anthropic | mistral
  model_env: LLM_MODEL      # read model id from env
```

### 8.2 Environment (secrets + model pin)

```
GROQ_API_KEY=
LLM_MODEL=qwen/...          # confirm exact Groq id
# Optional:
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GOOGLE_API_KEY=
# MISTRAL_API_KEY=
```

Never commit `.env`. Commit `.env.example` only.

---

## 9. Data contracts (stage artifacts)

### Raw document

```json
{
  "page_id": "hdfc_large_cap",
  "url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
  "fetched_at": "2026-11-01T10:00:00+05:30",
  "title": "...",
  "content": "..."
}
```

### Chunk

```json
{
  "chunk_id": "hdfc_large_cap_0003",
  "page_id": "hdfc_large_cap",
  "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
  "scraped_at": "2026-11-01T10:00:00+05:30",
  "strategy_id": "heading_aware_v1",
  "text": "..."
}
```

### Retrieval dump

```json
{
  "query_id": "...",
  "query": "Expense ratio of HDFC Large Cap?",
  "hits": [
    {"chunk_id": "...", "score": 0.82, "source_url": "...", "text": "..."}
  ]
}
```

### Generation dump

```json
{
  "query_id": "...",
  "answer": "...",
  "citation_url": "...",
  "last_updated_from_sources": "2026-11-01",
  "refused": false
}
```

These contracts make the RAG demo walkable stage-by-stage.

---

## 10. UI architecture

Minimal single-view prototype:

| Element | Behavior |
|---|---|
| Welcome line | States purpose: HDFC MF facts from Groww public pages |
| 3 example chips/buttons | Prefill the query box |
| Persistent banner | “Facts-only. No investment advice.” |
| Disclaimer | Same text as `deliverables/disclaimer.txt` |
| Answer panel | Answer text + one citation link + last-updated line |
| Optional debug panel | Show retrieval hits (supports W3 demo) |

No auth, no user profile, no file upload of statements containing PII.

---

## 11. Sequence: factual happy path

```
UI → Orchestrator: "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
Orchestrator → Guardrails: pass (no PII, factual)
Orchestrator → Embedder: query vector
Orchestrator → Chroma: top-k
Orchestrator → Artifact: write retrieval dump
Orchestrator → LLM: context + instructions
LLM → Orchestrator: ≤3 sentence answer
Orchestrator → Artifact: write generation dump
Orchestrator → UI: answer + citation + last updated
```

## 12. Sequence: advisory refuse path

```
UI → Orchestrator: "Should I buy HDFC Mid Cap?"
Orchestrator → Guardrails: advice detected
Orchestrator → UI: polite refuse + educational link
(no retrieval required; optional light retrieval only if needed to pick educational URL)
```

---

## 13. Non-functional considerations

| Area | Approach |
|---|---|
| Corpus size | Tiny (5 pages) — local Chroma is enough |
| Latency | Embed locally + Groq generation; keep top_k small |
| Freshness | `fetched_at` / `scraped_at` drive “Last updated from sources” |
| Reproducibility | Pin model ids in config/env; keep stage dumps |
| Security | Allowlist URLs; secrets in env; no PII persistence |
| Failure modes | Fetch failure → skip/flag page; empty retrieve → honest gap message; LLM down → surface error without fabricating |

---

## 14. Phased delivery map

| Phase | Architecture slice | Exit criteria |
|---|---|---|
| 1 | Loader + `data/raw` | 5 pages stored with URLs + timestamps |
| 2 | Chunker + `data/chunks` | Inspectable chunks; strategy documented |
| 3 | Embedder + Chroma upsert | Queryable collection; config-driven model/DB |
| 4 | Retriever + retrieval dumps | top-k + scores + source URLs for sample queries |
| 5 | Guardrails + LLM + UI | Facts answered with citation; advice refused; disclaimer visible |

---

## 15. Open architecture decisions

| Decision | Options | Default lean |
|---|---|---|
| UI framework | FastAPI / Streamlit / Gradio | FastAPI (HTML + `/api/ask`) |
| Chunking | Heading-aware vs fixed-size | Decide after inspecting Phase 1 HTML |
| Intent classifier | Rules-only vs small LLM call | Rules first for refuse paths |
| Multi-provider LLM | Adapter interface | Thin `llm_client` with provider switch |
| Educational refuse URL | One of 5 pages vs AMFI/SEBI | Prefer allowlisted Groww page; list extras in sources deliverable |

---

## 16. Out of scope for this architecture

- Multi-AMC crawl or continuous web scraping beyond the 5 pages
- User accounts, conversation memory with PII, or ticket systems
- Return analytics / ranking engines
- Production auth, rate limiting, or multi-tenant hosting (prototype-grade only)

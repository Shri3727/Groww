# PRD: Groww Mutual Fund FAQ Assistant

| Field | Value |
|---|---|
| Product | Facts-only FAQ assistant for HDFC Mutual Fund schemes on Groww |
| Status | Draft |
| Source | `Docs/Problemstatement.txt` |
| Type | Working RAG prototype (demo-oriented) |

---

## 1. Problem

Retail users and support/content teams repeatedly ask the same factual questions about mutual fund schemes (expense ratio, exit load, SIP minimum, ELSS lock-in, riskometer, benchmark, statement download). Answers today are scattered across public pages and easy to confuse with advice.

We will build a small FAQ assistant that answers **facts only** from a fixed set of official Groww public pages, with a mandatory source citation, and refuses advisory questions.

---

## 2. Goals

1. Answer factual MF scheme questions using only the approved public pages.
2. Show **exactly one clear source link** in every answer.
3. Refuse opinionated / portfolio / advice questions politely, with a facts-only message and a relevant educational link.
4. Demonstrate a full RAG pipeline with **each stage’s data persisted explicitly** for demo visibility.
5. Keep the UI tiny and clearly labeled: facts-only, no investment advice.

## 3. Non-goals

- Investment advice, buy/sell recommendations, or portfolio construction.
- Scraping any links beyond the 5 approved pages (no deep crawl of internal links).
- Performance calculation or returns comparison (link to official factsheet if asked).
- Collecting or storing PII (PAN, Aadhaar, account numbers, OTPs, emails, phones).
- Using third-party blogs, screenshots of app back-ends, or non-public sources.

---

## 4. Users

| Persona | Need |
|---|---|
| Retail user comparing schemes | Fast factual answers with a trustworthy source link |
| Support / content team | Deflect repetitive MF fact questions without giving advice |

---

## 5. Scope

### 5.1 Data sources (exactly these 5 pages)

| # | Page | URL |
|---|---|---|
| 1 | AMC overview — HDFC Mutual Fund | https://groww.in/mutual-funds/amc/hdfc-mutual-funds |
| 2 | Large Cap — HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 3 | Flexi Cap — HDFC Flexi Cap Direct Plan Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 4 | ELSS (tax saver) — HDFC ELSS Tax Saver Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 5 | Mid Cap — HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |

**Rule:** Scrape and store **only** these pages. Do not scrape links internal to these pages.

### 5.2 In-scope question types (examples)

- Expense ratio of \<scheme\>?
- ELSS lock-in?
- Minimum SIP?
- Exit load?
- Riskometer / benchmark?
- How to download capital-gains statement?

### 5.3 Out-of-scope question types (must refuse)

- “Should I buy/sell?”
- Portfolio allocation / “which fund is better for me?”
- Any request that requires computing or comparing returns
- Any request that involves PII

---

## 6. Product requirements

### 6.1 FAQ assistant behavior

| ID | Requirement |
|---|---|
| FR-1 | Answer factual queries only from retrieved corpus grounded in the 5 pages. |
| FR-2 | Every answer must include **one** clear citation/source link. |
| FR-3 | Answers must be **≤ 3 sentences**. |
| FR-4 | Every answer must include `Last updated from sources: <timestamp or date>`. |
| FR-5 | Refuse advisory/opinionated questions with a polite, facts-only message + relevant educational link. |
| FR-6 | Do not invent facts; if the corpus lacks the answer, say so and point to the closest official page. |
| FR-7 | Do not accept or store PII. |

### 6.2 UI (tiny prototype)

| ID | Requirement |
|---|---|
| UI-1 | Welcome line. |
| UI-2 | Exactly **3 example questions** users can try. |
| UI-3 | Persistent note: **“Facts-only. No investment advice.”** |
| UI-4 | Visible disclaimer snippet (facts-only, no advice) — same text used in deliverables. |
| UI-5 | Display the citation link prominently with each answer. |

### 6.3 Demo / observability (RAG stages)

Because this is a RAG demo, each pipeline stage must persist intermediate artifacts so they can be shown:

| Stage | What to store / show |
|---|---|
| Data loading | Raw scraped content from the 5 pages |
| Data chunking | Chunks + chosen chunking strategy metadata |
| Data embedding | Embedding artifacts / IDs mapped to chunks |
| Vector store | ChromaDB collection contents / queryable index |
| Retrieval | Retrieved chunks + scores for a query |
| Generation | Final LLM answer + citation |

---

## 7. Technical design (phased implementation)

Implement in phases. Model providers and key knobs must live in config / `.env` so they can be swapped without code changes.

### Phase 1 — Data loading

- Fetch HTML/text from the 5 approved URLs only.
- Persist raw page content + source URL + fetch timestamp.

### Phase 2 — Data chunking

- Chunk loaded documents using a strategy suited to the scraped content (agent may choose: e.g., section-aware, heading-based, or fixed-size with overlap).
- Persist chunks with source URL and chunk metadata.
- Document the chosen strategy in README / config comments.

### Phase 3 — Data embedding

| Item | Default | Configurability |
|---|---|---|
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` | Via config file |
| Vector DB | ChromaDB | Via config file |

### Phase 4 — Data retrieval

- Use the **same** embedding model as ingestion.
- Query the **same** ChromaDB collection used at ingestion.
- Return top-k chunks with source URLs for citation.

### Phase 5 — LLM answer generation

| Item | Spec |
|---|---|
| Primary provider | Groq (API key via `.env`) |
| Default model | `qwen/qwen3-8-27b` (exact ID from `.env`; correct if provider listing differs) |
| Alternate providers (config-ready) | Gemini, OpenAI, Anthropic, Mistral |
| Prompting | Instruction-style: identify exact fact → answer or refuse → concise phrasing → polite safe-refusal → citation wording |

**Config / secrets**

- Embedding model, vector DB settings, LLM provider, and model name → **config file**.
- API keys (Groq and any alternate providers) → **`.env`** (never commit secrets).

---

## 8. Constraints & compliance

| Constraint | Detail |
|---|---|
| Public sources only | Groww official public pages listed above; no app back-end screenshots; no third-party blogs as sources |
| No PII | Do not accept/store PAN, Aadhaar, account numbers, OTPs, emails, phone numbers |
| No performance claims | Do not compute/compare returns; if asked, link to official factsheet / page |
| Clarity & transparency | ≤3 sentences; include `Last updated from sources:` |
| No advice | Refuse buy/sell / suitability questions |

---

## 9. Deliverables

| # | Deliverable |
|---|---|
| 1 | Working prototype link (app/notebook), **or** ≤3-min demo video if hosting isn’t possible |
| 2 | Source list (CSV or MD) of the **15–25 URLs** used (the 5 scrape targets plus any educational/refusal links cited) |
| 3 | README: setup steps, scope (AMC + schemes), known limits |
| 4 | Sample Q&A file: **5–10** queries with assistant answers + links |
| 5 | Disclaimer snippet used in the UI (facts-only, no advice) |

---

## 10. Skills / evaluation focus

| Skill | What “good” looks like |
|---|---|
| W1 — Thinking like a model | Correctly identify the exact fact asked; decide answer vs refuse |
| W2 — LLMs & prompting | Clear instructions, concise answers, polite safe-refusals, solid citation wording |
| W3 — RAG only | Small-corpus retrieval with accurate citations grounded in AMC / official public pages |

---

## 11. Success criteria

1. Prototype answers the listed factual question types with a valid source link.
2. Advisory questions are refused with the required tone and an educational link.
3. Pipeline stages (load → chunk → embed → store → retrieve → generate) are inspectable via stored artifacts.
4. Embedding model, ChromaDB, and LLM provider/model are configurable without code edits.
5. All five submission deliverables are present and consistent with the UI disclaimer.

---

## 12. Open decisions

| Topic | Notes |
|---|---|
| Exact Groq model ID | Problem statement lists `qwen/qwen3.8-27b`; confirm against Groq’s current model catalog and pin in `.env` |
| Chunking strategy | Chosen during Phase 2 based on scraped page structure; document in README |
| “Last updated from sources” format | Prefer ISO date from scrape timestamp |
| Educational link for refusals | Prefer one of the 5 official pages or a clearly official Groww/AMFI/SEBI educational URL listed in the source list |
| Hosting vs demo video | Prefer hosted prototype; fall back to ≤3-min video |

---

## 13. Suggested example questions (UI)

1. What is the expense ratio of HDFC Large Cap Fund Direct Growth?
2. What is the lock-in period for HDFC ELSS Tax Saver Fund?
3. How do I download a capital-gains statement?

*(Final three may be refined once scraped content confirms available fields.)*

# Groww Mutual Fund FAQ Assistant

Facts-only RAG prototype for **Groww**, covering **HDFC Mutual Fund** and four Direct Growth schemes. No investment advice.

## Submission links

| Field | Value |
|---|---|
| **GitHub** | https://github.com/Shri3727/Groww |
| **Working prototype** | https://groww-nqm9.vercel.app |
| **Demo video** | Not required — prototype is hosted |

---

## Scope

- **Product:** Groww
- **AMC:** HDFC Mutual Fund
- **Schemes (4):** Large Cap, Flexi Cap, ELSS Tax Saver, Mid Cap (Direct Growth / Direct Plan Growth on Groww)

## What it does

- Answers factual questions only (expense ratio, exit load, min SIP, ELSS lock-in, riskometer/benchmark, how to download statements).
- Every answer includes **one citation URL**.
- Refuses buy/sell advice, return comparisons, PII, and out-of-scope funds, with an educational/official link.
- Tiny UI: welcome line, **3 example questions**, banner **“Facts-only. No investment advice.”**
- Answers are short (≤3 sentences) and include **Last updated from sources:** when grounded.

## Disclaimer (used in the UI)

```
Facts-only. No investment advice.

This assistant answers factual questions about selected HDFC Mutual Fund schemes using official Groww public pages only. It does not recommend buying or selling, does not compute or compare returns, and does not accept PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers.
```

File: [`deliverables/disclaimer.txt`](deliverables/disclaimer.txt)

---

## Source list (20 URLs)

Full table: [`deliverables/sources.md`](deliverables/sources.md)

**Indexed for retrieval (Groww public scheme pages):**

1. https://groww.in/mutual-funds/amc/hdfc-mutual-funds
2. https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
3. https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth
4. https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth
5. https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
6. https://groww.in/help

**Official AMC / AMFI / SEBI (education, factsheets, KIM/SID, riskometer, TER):**

7. https://www.hdfcfund.com/
8. https://www.hdfcfund.com/statutory-disclosure
9. https://www.hdfcfund.com/mutual-funds/factsheets
10. https://www.hdfcfund.com/mutual-funds/fund-documents/kim
11. https://www.hdfcfund.com/statutory-disclosure/riskometers
12. https://www.amfiindia.com/
13. https://www.amfiindia.com/investor-corner/knowledge-center
14. https://www.amfiindia.com/net-asset-value/nav-history
15. https://www.amfiindia.com/otherdata/statement-of-Additional-Information
16. https://www.sebi.gov.in/
17. https://investor.sebi.gov.in/
18. https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=8  
(plus statutory TER / SID hub on the HDFC disclosure page — see sources.md for 20 rows)

---

## Sample Q&A

Full file: [`deliverables/sample_qa.md`](deliverables/sample_qa.md)

| Q | A (short) | Citation |
|---|---|---|
| Expense ratio of HDFC Large Cap Direct Growth? | Expense ratio 1.02%. Last updated from sources: 2026-11-01. | [Groww Large Cap](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) |
| Exit load of HDFC Mid Cap Direct Growth? | 1% if redeemed within 1 year. Last updated from sources: 2026-11-01. | [Groww Mid Cap](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| Minimum SIP for HDFC Flexi Cap? | Minimum SIP ₹100. Last updated from sources: 2026-11-01. | [Groww Flexi Cap](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth) |
| Benchmark of HDFC Large Cap? | NIFTY 100 Total Return Index. Last updated from sources: 2026-11-01. | [Groww Large Cap](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) |
| ELSS lock-in? | Mandatory 3-year lock-in from each investment. Last updated from sources: 2026-11-01. | [Groww ELSS](https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth) |
| How to download capital-gains statement? | Download from Groww Reports/Statements after login; do not share PII here. | [Groww Help](https://groww.in/help) |
| Should I buy HDFC Mid Cap? | **Refuse.** Facts only; see SEBI investor education. | [SEBI investor](https://investor.sebi.gov.in/) |
| Which fund has better returns? | **Refuse.** No return comparison; use official factsheet. | [HDFC factsheets](https://www.hdfcfund.com/mutual-funds/factsheets) |
| Expense ratio of Parag Parikh Flexi Cap? | **Refuse.** Out of corpus. | Groww HDFC Flexi Cap page |
| My PAN is ABCDE1234F, what’s my tax? | **Refuse.** No PII. | Groww HDFC AMC page |

---

## Setup (local)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Ingest (scrape → chunk → embed → Chroma):

```bash
python scripts/run_ingest.py --phase all
```

Run UI:

```bash
uvicorn src.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

On **Vercel**, retrieval is **lexical** over committed `data/chunks/*.jsonl` (no PyTorch/Chroma).

## Known limits

- Retrieval corpus is the five Groww HDFC pages (plus a lock-in fact chunk and Groww Help for statements).
- Groww is the chosen product; scheme facts are taken from Groww public pages, not from AMC PDF dumps inside the vector index.
- Does not compute or compare returns.
- Does not accept PAN / Aadhaar / OTPs / emails / phones.
- ELSS tax computation is refused; lock-in is stated as the 3-year statutory ELSS lock-in.
- Local Chroma + MiniLM vs Vercel lexical answers can differ slightly in wording.

## API

- `GET /api/health`
- `POST /api/retrieve` `{"question":"..."}`
- `POST /api/ask` `{"question":"..."}`

"""FastAPI UI + retrieval API for the MF FAQ assistant."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.app.orchestrator import DISCLAIMER, EXAMPLE_QUESTIONS, ask
from src.config import load_settings
from src.retrieve.search import retrieve
from src.runtime import is_vercel, retrieval_backend

app = FastAPI(
    title="Groww MF FAQ Assistant",
    description="Facts-only RAG prototype over selected HDFC Mutual Fund pages on Groww.",
    version="0.1.0",
)


@app.on_event("startup")
def _startup_warmup():
    if is_vercel() or retrieval_backend() == "lexical":
        print("[app] lexical retrieval — skip embedding warmup")
        return
    from src.ingest.embed import warmup

    name = warmup()
    print(f"[app] embedding warmup complete: {name}")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


@app.get("/api/health")
def health():
    settings = load_settings()
    backend = retrieval_backend(settings)
    return {
        "ok": True,
        "sources": len(settings.get("sources", [])),
        "backend": backend,
        "vercel": is_vercel(),
        "collection": settings.get("vector_db", {}).get("collection"),
        "embedding_model": (
            "lexical-idf"
            if backend == "lexical"
            else settings.get("embedding", {}).get("model")
        ),
    }


@app.get("/api/meta")
def meta():
    return {
        "disclaimer": DISCLAIMER,
        "banner": "Facts-only. No investment advice.",
        "examples": EXAMPLE_QUESTIONS,
        "welcome": "Ask factual questions about selected HDFC Mutual Fund schemes (Groww public pages).",
    }


@app.post("/api/retrieve")
def api_retrieve(body: RetrieveRequest):
    try:
        return retrieve(body.question, top_k=body.top_k, persist=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/ask")
def api_ask(body: AskRequest):
    try:
        return ask(body.question)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def index():
    examples_html = "\n".join(
        f'<button type="button" class="example" data-q="{q}">{q}</button>'
        for q in EXAMPLE_QUESTIONS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HDFC MF FAQ · Facts only</title>
  <style>
    :root {{
      --bg: #f3f6f4;
      --ink: #14201b;
      --muted: #5b6b63;
      --accent: #0f6b4c;
      --card: #ffffff;
      --line: #d7e0db;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(1200px 500px at 10% -10%, #d9efe4 0%, transparent 55%),
        radial-gradient(900px 400px at 100% 0%, #e7eef5 0%, transparent 50%),
        var(--bg);
      color: var(--ink);
    }}
    main {{
      max-width: 820px;
      margin: 0 auto;
      padding: 2rem 1.25rem 3rem;
    }}
    h1 {{
      font-size: 1.75rem;
      margin: 0 0 0.35rem;
      letter-spacing: -0.02em;
    }}
    .welcome {{ color: var(--muted); margin-bottom: 1rem; }}
    .banner {{
      display: inline-block;
      background: #e7f5ee;
      color: var(--accent);
      border: 1px solid #b9ddcb;
      padding: 0.35rem 0.7rem;
      font-weight: 600;
      font-size: 0.9rem;
      margin-bottom: 1rem;
    }}
    .disclaimer {{
      color: var(--muted);
      font-size: 0.9rem;
      border-left: 3px solid var(--line);
      padding-left: 0.75rem;
      margin-bottom: 1.25rem;
    }}
    .examples {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
    }}
    .example {{
      text-align: left;
      background: var(--card);
      border: 1px solid var(--line);
      padding: 0.7rem 0.85rem;
      cursor: pointer;
      color: var(--ink);
    }}
    .example:hover {{ border-color: var(--accent); }}
    form {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
    }}
    input[type=text] {{
      flex: 1;
      padding: 0.8rem 0.9rem;
      border: 1px solid var(--line);
      font-size: 1rem;
    }}
    button.ask {{
      background: var(--accent);
      color: white;
      border: 0;
      padding: 0 1.1rem;
      font-weight: 600;
      cursor: pointer;
    }}
    button.ask:disabled {{
      opacity: 0.6;
      cursor: wait;
    }}
    .loading {{ color: var(--muted); font-style: italic; }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      padding: 1rem 1.1rem;
      margin-bottom: 1rem;
    }}
    .panel h2 {{
      margin: 0 0 0.6rem;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
    }}
    .answer {{ white-space: pre-wrap; line-height: 1.45; }}
    .meta a {{ color: var(--accent); }}
    .hit {{
      border-top: 1px solid var(--line);
      padding: 0.75rem 0;
      font-size: 0.92rem;
    }}
    .hit:first-child {{ border-top: 0; }}
    .score {{ color: var(--muted); font-size: 0.85rem; }}
    .error {{ color: #8b1e1e; }}
    details summary {{ cursor: pointer; color: var(--muted); }}
  </style>
</head>
<body>
  <main>
    <h1>HDFC Mutual Fund FAQ</h1>
    <p class="welcome">Ask factual questions about selected HDFC schemes using official Groww public pages.</p>
    <div class="banner">Facts-only. No investment advice.</div>
    <p class="disclaimer">{DISCLAIMER}</p>

    <div class="examples">{examples_html}</div>

    <form id="ask-form">
      <input id="question" type="text" placeholder="e.g. Expense ratio of HDFC Large Cap?" autocomplete="off" />
      <button class="ask" type="submit">Ask</button>
    </form>

    <div class="panel" id="answer-panel" hidden>
      <h2>Answer</h2>
      <div class="answer" id="answer"></div>
      <p class="meta" id="meta"></p>
    </div>

    <details class="panel" id="hits-panel" hidden>
      <summary>Show retrieval hits</summary>
      <div id="hits"></div>
    </details>
    <p class="error" id="error"></p>
  </main>
  <script>
    const form = document.getElementById('ask-form');
    const input = document.getElementById('question');
    const answerPanel = document.getElementById('answer-panel');
    const hitsPanel = document.getElementById('hits-panel');
    const answerEl = document.getElementById('answer');
    const metaEl = document.getElementById('meta');
    const hitsEl = document.getElementById('hits');
    const errorEl = document.getElementById('error');

    const askBtn = document.querySelector('button.ask');
    let inflight = false;

    async function askQuestion(question) {{
      if (inflight) return;
      inflight = true;
      askBtn.disabled = true;
      errorEl.textContent = '';
      answerPanel.hidden = false;
      hitsPanel.hidden = true;
      answerEl.className = 'answer loading';
      answerEl.textContent = 'Looking up facts (first question can take ~20 seconds)...';
      metaEl.innerHTML = '';
      try {{
        const res = await fetch('/api/ask', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ question }})
        }});
        const data = await res.json();
        if (!res.ok) {{
          const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
          throw new Error(detail || 'Request failed');
        }}
        answerEl.className = 'answer';
        answerEl.textContent = data.answer || '(empty answer)';
        const parts = [];
        if (data.citation_url) parts.push('Source: <a href="' + data.citation_url + '" target="_blank" rel="noopener">' + data.citation_url + '</a>');
        if (data.last_updated_from_sources) parts.push('Last updated from sources: ' + data.last_updated_from_sources);
        if (data.refused) parts.push('Refused: ' + (data.reason || 'policy'));
        metaEl.innerHTML = parts.join(' · ');
        hitsEl.innerHTML = (data.hits || []).map(h => `
          <div class="hit">
            <div class="score">score ${{h.score}} · ${{h.page_id || ''}} · ${{h.section || 'section n/a'}}</div>
            <div>${{(h.text || '').replace(/</g,'&lt;').slice(0,500)}}</div>
            <div><a href="${{h.source_url}}" target="_blank" rel="noopener">${{h.source_url}}</a></div>
          </div>`).join('');
        hitsPanel.hidden = !(data.hits && data.hits.length);
      }} catch (err) {{
        answerEl.className = 'answer';
        answerEl.textContent = '';
        errorEl.textContent = err.message || String(err);
      }} finally {{
        inflight = false;
        askBtn.disabled = false;
      }}
    }}

    document.querySelectorAll('.example').forEach(btn => {{
      btn.addEventListener('click', () => {{
        input.value = btn.dataset.q;
        askQuestion(btn.dataset.q);
      }});
    }});

    form.addEventListener('submit', (e) => {{
      e.preventDefault();
      const question = input.value.trim();
      if (!question) {{
        errorEl.textContent = 'Type a question or click an example.';
        return;
      }}
      askQuestion(question);
    }});
  </script>
</body>
</html>"""

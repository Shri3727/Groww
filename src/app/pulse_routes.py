"""Product-pulse page and approval-gated logging endpoints."""

from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.pulse.analyze import analyze
from src.pulse.compose import build_package
from src.pulse.store import commit_approved, write_pulse_preview

router = APIRouter()


class ApproveRequest(BaseModel):
    approved: bool = False


def current_package() -> dict:
    package = build_package(analyze())
    write_pulse_preview(package)
    return package


def _render(package: dict, notice: str = "") -> str:
    themes = "".join(
        f"<li>{html.escape(theme['label'])} — {theme['count']} reviews</li>"
        for theme in package["themes"]
    )
    quotes = "".join(
        "<blockquote>"
        f"<p>“{html.escape(quote['text'])}”</p>"
        f"<p class='meta'>{html.escape(quote['review_id'])} · {html.escape(quote['date'])}</p>"
        "</blockquote>"
        for quote in package["quotes"]
    )
    bullets = "".join(f"<li>{html.escape(line)}</li>" for line in package["explanation_bullets"])
    links = "".join(
        f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></li>'
        for url in package["source_list"]
    )
    notice_html = f"<p class='notice'>{html.escape(notice)}</p>" if notice else ""
    pulse = html.escape(package["weekly_pulse"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Weekly product pulse</title>
  <style>
    :root {{ --bg:#f3f6f4; --ink:#14201b; --muted:#5b6b63; --accent:#0f6b4c; --card:#fff; --line:#d7e0db; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family:"Segoe UI","Helvetica Neue",sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ max-width: 820px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
    a {{ color: var(--accent); }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }}
    .card {{ background: var(--card); border: 1px solid var(--line); padding: 1rem 1.1rem; margin: 1rem 0; }}
    pre {{ white-space: pre-wrap; font-family: inherit; margin: 0; line-height: 1.45; }}
    blockquote {{ margin: 0.6rem 0; padding-left: 0.8rem; border-left: 3px solid var(--line); }}
    .meta {{ color: var(--muted); font-size: 0.85rem; }}
    .notice {{ background: #e5f4ec; border: 1px solid #b7dcc8; padding: 0.7rem 0.8rem; }}
    button {{ background: var(--accent); color: white; border: 0; padding: 0.7rem 1rem; font-weight: 600; cursor: pointer; }}
    button:disabled {{ opacity: 0.45; cursor: not-allowed; }}
    label {{ display: flex; gap: 0.5rem; align-items: flex-start; margin-bottom: 0.8rem; }}
  </style>
</head>
<body>
<main>
  <p><a href="/">FAQ assistant</a></p>
  <h1>Weekly product pulse</h1>
  <p class="meta">{package['review_count']} reviews · {package['window']['start']} to {package['window']['end']} · {package['weekly_pulse_words']} words</p>
  {notice_html}
  <section class="card">
    <h2>Themes (max 5)</h2>
    <ol>{themes}</ol>
    <p class="meta">Top 3: {html.escape(", ".join(package["top_themes"]))}</p>
  </section>
  <section class="card">
    <h2>User quotes</h2>
    {quotes}
  </section>
  <section class="card">
    <h2>Weekly pulse</h2>
    <pre>{pulse}</pre>
  </section>
  <section class="card">
    <h2>Fee explainer</h2>
    <p>{html.escape(package["fee_name"])}</p>
    <ul>{bullets}</ul>
    <p>Last checked: {html.escape(package["last_checked"])}</p>
    <ul>{links}</ul>
  </section>
  <section class="card">
    <h2>Approval</h2>
    <p>Nothing is written to the notes log or the email draft until you approve. The draft is not sent.</p>
    <form id="approve-form">
      <label>
        <input id="approve-check" type="checkbox" />
        I approve appending this entry to the notes doc and creating an email draft.
      </label>
      <button id="approve-btn" type="submit" disabled>Approve and log</button>
    </form>
    <p id="result" class="meta"></p>
  </section>
</main>
<script>
  const check = document.getElementById('approve-check');
  const button = document.getElementById('approve-btn');
  const result = document.getElementById('result');
  check.addEventListener('change', () => {{ button.disabled = !check.checked; }});
  document.getElementById('approve-form').addEventListener('submit', async (event) => {{
    event.preventDefault();
    if (!check.checked) return;
    button.disabled = true;
    result.textContent = 'Logging…';
    const response = await fetch('/api/pulse/approve', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ approved: true }})
    }});
    const data = await response.json();
    if (!response.ok) {{
      result.textContent = data.detail || 'Approval failed';
      button.disabled = false;
      return;
    }}
    result.textContent = 'Saved notes and email draft. Nothing was sent.';
  }});
</script>
</body>
</html>"""


@router.get("/pulse", response_class=HTMLResponse)
def pulse_page():
    return _render(current_package())


@router.get("/api/pulse")
def pulse_api():
    return current_package()


@router.post("/api/pulse/approve")
def pulse_approve(body: ApproveRequest):
    if not body.approved:
        raise HTTPException(status_code=400, detail="Approval is required before logging.")
    package = current_package()
    paths = commit_approved(package)
    return {"ok": True, "sent": False, **paths}

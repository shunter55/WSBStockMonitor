from __future__ import annotations
# HTML report generation for WSB Stock Monitor

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


def _format_generated_at(raw: str) -> str:
    try:
        dt = datetime.fromisoformat(raw)
        tz_name = dt.strftime("%Z") or "UTC"
        return html.escape(dt.strftime(f"%b %-d, %Y at %-I:%M %p {tz_name}"))
    except (ValueError, TypeError):
        return html.escape(str(raw))


def write_html_report(report: dict[str, Any], path: Path) -> Path:
    path.write_text(render_html(report), encoding="utf-8")
    return path


def render_html(report: dict[str, Any]) -> str:
    generated = _format_generated_at(report.get("generated_at", ""))
    subreddit = html.escape(str(report.get("subreddit", "wallstreetbets")))
    window = html.escape(str(report.get("window_hours", 48)))

    sources = report.get("sources") or {}
    if not sources and report.get("sections"):
        sources = {"gemini": {"sections": report["sections"]}}

    gemini_data = sources.get("gemini") or {}
    content = _render_gemini_content(gemini_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WSB Stock Monitor — {subreddit}</title>
  <style>
    :root {{
      --bg: #0b0e11;
      --card: #161b22;
      --text: #e6edf3;
      --muted: #8b949e;
      --bull: #3fb950;
      --bear: #f85149;
      --accent: #58a6ff;
      --border: #30363d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 1.5rem;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; }}
    header {{ margin-bottom: 1.5rem; }}
    h1 {{ margin: 0 0 0.25rem; font-size: 1.75rem; }}
    .meta {{ color: var(--muted); font-size: 0.95rem; }}
    .panel-meta {{
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0 0 1.25rem;
    }}
    .source-block {{
      margin-bottom: 1.5rem;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}
    .source-block h2 {{
      margin: 0;
      padding: 1rem 1.25rem;
      font-size: 1.05rem;
      background: #21262d;
      border-bottom: 1px solid var(--border);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      padding: 0.65rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      font-size: 0.8rem;
      text-transform: uppercase;
    }}
    tr:last-child td {{ border-bottom: none; }}
    .ticker {{ font-weight: 700; }}
    .ticker a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .ticker a:hover {{ text-decoration: underline; }}
    .bull {{ color: var(--bull); }}
    .bear {{ color: var(--bear); }}
    .muted {{ color: var(--muted); }}
    .stats {{ padding: 0.75rem 1.25rem; color: var(--muted); font-size: 0.85rem; }}
    .empty {{
      background: var(--card);
      border: 1px dashed var(--border);
      border-radius: 12px;
      color: var(--muted);
      padding: 2rem;
      text-align: center;
    }}
    footer {{
      margin-top: 2rem;
      color: var(--muted);
      font-size: 0.85rem;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>r/{subreddit} — WSB Stock Monitor</h1>
      <p class="meta">Generated {generated} · {window}h window</p>
    </header>
    {content}
    <footer>WSB Stock Monitor</footer>
  </div>
</body>
</html>
"""


def _render_gemini_content(source_data: dict[str, Any]) -> str:
    sections = source_data.get("sections") or []

    meta_parts: list[str] = []
    if model := source_data.get("model"):
        meta_parts.append(f"Model: {html.escape(str(model))}")
    if source_data.get("use_grounding"):
        meta_parts.append("Google Search grounding enabled")

    meta_html = ""
    if meta_parts:
        meta_html = f'<p class="panel-meta">{" · ".join(meta_parts)}</p>\n    '

    if not sections:
        return (
            f'{meta_html}<div class="empty">No Gemini data in this report.</div>'
        )

    return meta_html + "\n".join(_render_section(section) for section in sections)


def _google_finance_url(ticker: str, exchange: str = "NASDAQ") -> str:
    symbol = ticker.strip().upper()
    return f"https://www.google.com/finance/beta/quote/{quote(symbol)}:{exchange}"


def _format_mentions_cell(stock: dict[str, Any]) -> str:
    metric = str(stock.get("mention_metric") or "").strip()
    value = stock.get("mention_value")
    if value is not None and value != "":
        value_text = str(value)
        if metric:
            return f"{metric}: {value_text}"
        return value_text
    if growth := stock.get("mention_growth_pct"):
        prefix = f"{metric}: " if metric else ""
        return f"{prefix}+{growth}%"
    if metric:
        return metric
    return "—"


def _render_ticker_cell(ticker_raw: str) -> str:
    symbol = str(ticker_raw).strip().upper()
    label = html.escape(symbol or "?")
    if not symbol or symbol == "?":
        return f'<td class="ticker">{label}</td>'
    url = html.escape(_google_finance_url(symbol), quote=True)
    return (
        f'<td class="ticker">'
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        f"</td>"
    )


def _render_section(section: dict[str, Any]) -> str:
    title = html.escape(section.get("title", "Section"))
    stocks = section.get("parsed", {}).get("stocks") or []
    rows: list[str] = []

    for index, stock in enumerate(stocks):
        rank = stock.get("rank", index + 1)
        mentions = html.escape(_format_mentions_cell(stock))
        bull = html.escape(str(stock.get("bullish_pct", "?")))
        bear = html.escape(str(stock.get("bearish_pct", "?")))
        rows.append(
            f"<tr>"
            f"<td>#{rank}</td>"
            f"{_render_ticker_cell(str(stock.get('ticker', '?')))}"
            f"<td>{mentions}</td>"
            f'<td class="bull">{bull}%</td>'
            f'<td class="bear">{bear}%</td>'
            f"</tr>"
        )

    table_body = "\n".join(rows) if rows else '<tr><td colspan="5">No tickers found</td></tr>'

    stats_html = ""
    stats = section.get("stats")
    if stats:
        stats_html = (
            f'<p class="stats">Scanned {stats.get("posts_scanned", "?")} posts, '
            f'{stats.get("comments_scanned", "?")} comments '
            f'({html.escape(str(stats.get("data_source", "reddit")))})</p>'
        )

    return f"""
      <section class="source-block">
        <h2>{title}</h2>
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Ticker</th>
              <th>Mentions</th>
              <th>Bullish</th>
              <th>Bearish</th>
            </tr>
          </thead>
          <tbody>
            {table_body}
          </tbody>
        </table>
        {stats_html}
      </section>"""


def html_from_json_file(json_path: Path, html_path: Path | None = None) -> Path:
    report = json.loads(json_path.read_text(encoding="utf-8"))
    out = html_path or json_path.with_suffix(".html")
    return write_html_report(report, out)

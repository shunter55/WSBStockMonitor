from __future__ import annotations
# HTML report generation for WSB Stock Monitor

import base64
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from wsb_monitor.parser import normalize_exchange

DEFAULT_EXCHANGE = "NASDAQ"
_ASSETS = Path(__file__).parent / "assets"


def _b64_data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _generated_at_markup(raw: str) -> str:
    """ISO timestamp in datetime=; browser script formats to local time."""
    iso = str(raw or "").strip()
    if not iso:
        return html.escape("unknown")
    escaped = html.escape(iso)
    return f'<time id="report-generated-at" datetime="{escaped}">{escaped}</time>'


def write_html_report(report: dict[str, Any], path: Path) -> Path:
    path.write_text(render_html(report), encoding="utf-8")
    return path


def render_html(report: dict[str, Any]) -> str:
    generated = _generated_at_markup(report.get("generated_at", ""))
    subreddit = html.escape(str(report.get("subreddit", "wallstreetbets")))
    window = html.escape(str(report.get("window_hours", 48)))

    favicon_uri = _b64_data_uri(_ASSETS / "favicon.ico", "image/x-icon")
    bull_uri = _b64_data_uri(_ASSETS / "bull.png", "image/png")
    bear_uri = _b64_data_uri(_ASSETS / "bear.png", "image/png")

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
  <link rel="icon" href="{favicon_uri}">
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
    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 1.5rem;
    }}
    .header-text {{ flex: 1; }}
    h1 {{ margin: 0 0 0.25rem; font-size: 1.75rem; }}
    .meta {{ color: var(--muted); font-size: 0.95rem; }}
    .header-icons {{ display: flex; align-items: flex-end; gap: 0; }}
    .header-icons img {{ height: 80px; width: auto; }}
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
    .confidence {{ font-weight: 600; color: var(--accent); }}
    .summary {{ color: var(--muted); font-size: 0.9rem; max-width: 28rem; }}
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
      <div class="header-text">
        <h1>r/{subreddit} — WSB Stock Monitor</h1>
        <p class="meta">Generated {generated} · {window}h window</p>
      </div>
      <div class="header-icons">
        <img src="{bear_uri}" alt="bear">
        <img src="{bull_uri}" alt="bull">
      </div>
    </header>
    {content}
    <footer>WSB Stock Monitor</footer>
  </div>
  <script>
    (function () {{
      const el = document.getElementById("report-generated-at");
      if (!el || !el.dateTime) return;
      const date = new Date(el.dateTime);
      if (Number.isNaN(date.getTime())) return;
      el.textContent = new Intl.DateTimeFormat(undefined, {{
        dateStyle: "medium",
        timeStyle: "short",
      }}).format(date);
    }})();
  </script>
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
        return f'{meta_html}<div class="empty">No Gemini data in this report.</div>'

    return meta_html + "\n".join(_render_section(section) for section in sections)


def _google_finance_url(ticker: str, exchange: str | None = None) -> str:
    symbol = ticker.strip().upper()
    suffix = normalize_exchange(exchange or DEFAULT_EXCHANGE)
    return f"https://www.google.com/finance/beta/quote/{quote(symbol)}:{suffix}"


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


def _render_ticker_cell(stock: dict[str, Any]) -> str:
    symbol = str(stock.get("ticker", "?")).strip().upper()
    label = html.escape(symbol or "?")
    if not symbol or symbol == "?":
        return f'<td class="ticker">{label}</td>'
    url = html.escape(
        _google_finance_url(symbol, stock.get("exchange")),
        quote=True,
    )
    return (
        f'<td class="ticker">'
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        f"</td>"
    )


def _render_section(section: dict[str, Any]) -> str:
    if section.get("id") == "two_week_outlook":
        return _render_outlook_section(section)
    return _render_mentions_section(section)


def _render_mentions_section(section: dict[str, Any]) -> str:
    title = html.escape(section.get("title", "Section"))
    stocks = section.get("parsed", {}).get("stocks") or []
    rows: list[str] = []

    for index, stock in enumerate(stocks):
        rank = stock.get("rank", index + 1)
        mentions = html.escape(_format_mentions_cell(stock))
        bull_pct = stock.get("bullish_pct")
        bear_pct = stock.get("bearish_pct")
        bull = html.escape(str(bull_pct if bull_pct is not None else "?"))
        bear = html.escape(str(bear_pct if bear_pct is not None else "?"))
        rows.append(
            f"<tr>"
            f"<td>#{rank}</td>"
            f"{_render_ticker_cell(stock)}"
            f"<td>{mentions}</td>"
            f'<td class="bull">{bull}%</td>'
            f'<td class="bear">{bear}%</td>'
            f"</tr>"
        )

    table_body = "\n".join(rows) if rows else '<tr><td colspan="5">No tickers found</td></tr>'
    return _wrap_section_table(
        title,
        headers=("Rank", "Ticker", "Mentions", "Bullish", "Bearish"),
        table_body=table_body,
        stats=section.get("stats"),
    )


def _render_outlook_section(section: dict[str, Any]) -> str:
    title = html.escape(section.get("title", "Section"))
    stocks = section.get("parsed", {}).get("stocks") or []
    rows: list[str] = []

    for index, stock in enumerate(stocks):
        rank = stock.get("rank", index + 1)
        confidence = stock.get("confidence_pct")
        confidence_text = html.escape(
            str(confidence if confidence is not None else "?")
        )
        summary = html.escape(str(stock.get("summary") or "—"))
        rows.append(
            f"<tr>"
            f"<td>#{rank}</td>"
            f"{_render_ticker_cell(stock)}"
            f'<td class="confidence">{confidence_text}%</td>'
            f'<td class="summary">{summary}</td>'
            f"</tr>"
        )

    table_body = "\n".join(rows) if rows else '<tr><td colspan="4">No tickers found</td></tr>'
    return _wrap_section_table(
        title,
        headers=("Rank", "Ticker", "Confidence", "Why (2-week outlook)"),
        table_body=table_body,
        stats=section.get("stats"),
    )


def _wrap_section_table(
    title: str,
    *,
    headers: tuple[str, ...],
    table_body: str,
    stats: dict[str, Any] | None = None,
) -> str:
    header_row = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    stats_html = ""
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
            <tr>{header_row}</tr>
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

# WSB Stock Monitor

Raspberry Pi–friendly Python app for r/wallstreetbets stock mention tracking:

1. **Top 10 most mentioned** tickers in the last 48 hours  
2. **Top 10 fastest mention growth** (last 48h vs prior 48h)  

Each entry includes **bullish %** and **bearish %** sentiment.

## Data sources

| Source | What it provides |
|--------|------------------|
| **Reddit public JSON** (default, no API key) | Real mention counts from public WSB posts |
| **Reddit OAuth** (optional) | Same, plus comments if Reddit approved your app |
| **Gemini API** (optional) | AI-generated estimates for comparison |

Configure one or both. **You do not need a Reddit client ID/secret** for the default mode.

## Quick start

```bash
cd WSBStockMonitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Reddit credentials (and optionally Gemini)
python -m wsb_monitor
```

### Reddit without an API key (default)

If Reddit won’t give you a client ID/secret, use **public mode** (already the default when those are unset):

```bash
REDDIT_AUTH_MODE=public
REDDIT_USER_AGENT=wsbstockmonitor:1.0 (by /u/your_reddit_username)
python -m wsb_monitor --reddit-only
```

This reads `https://www.reddit.com/r/wallstreetbets/new.json` (no OAuth). It scans post titles/bodies only (comments off by default to stay within rate limits). Be polite: keep `REDDIT_REQUEST_DELAY_SEC=2` or higher.

### Reddit OAuth (optional, if you get approved)

Reddit has tightened access; many new apps need [approval](https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164).

1. [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) or [old.reddit.com/prefs/apps](https://old.reddit.com/prefs/apps)
2. Create a **script** app → copy client id + secret
3. Set `REDDIT_AUTH_MODE=oauth` and add `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`

### Run modes

```bash
python -m wsb_monitor run --reddit-only    # fetch data (recommended)
python -m wsb_monitor run --open             # run + open HTML in browser
python -m wsb_monitor serve --open           # view latest report anytime
```

Shorthand (same as `run`):

```bash
python -m wsb_monitor --reddit-only
python -m wsb_monitor --dry-run
```

Reports are saved to `data/reports/`:

- `wsb_report_<timestamp>.json` — raw data
- `wsb_report_<timestamp>.html` — webpage
- `latest.html` — always points to the most recent run

## Configuration

| Variable | Description |
|----------|-------------|
| `REDDIT_AUTH_MODE` | `auto` (default), `public`, or `oauth` |
| `REDDIT_USER_AGENT` | Required descriptive user agent |
| `REDDIT_CLIENT_ID` | Only for OAuth mode |
| `REDDIT_CLIENT_SECRET` | Only for OAuth mode |
| `REDDIT_REQUEST_DELAY_SEC` | Pause between requests in public mode (default `2`) |
| `REDDIT_SUBREDDIT` | Subreddit (default `wallstreetbets`) |
| `REDDIT_MAX_POSTS` | Max posts to scan per run (default `2000`) |
| `REDDIT_MAX_COMMENTS_PER_POST` | Comments per post (default `30`, `0` to skip) |
| `GEMINI_API_KEY` | Optional Gemini key |
| `GEMINI_MODEL` | Model id (default `gemini-2.5-flash`) |
| `GEMINI_USE_GROUNDING` | `true` enables Google Search (cannot use native JSON schema; see note below) |
| `WSB_WINDOW_HOURS` | Analysis window (default `48`) |
| `WSB_OUTPUT_DIR` | Report directory |

## Gemini grounding note

`GEMINI_USE_GROUNDING=true` turns on Google Search for fresher answers. The Gemini API does not allow grounding and structured `application/json` output in the same request, so with grounding enabled the app asks for JSON in the prompt and parses the text response instead.

## How Reddit analysis works

- Scans recent submissions (and optional comments) from r/wallstreetbets
- Detects tickers via `$TICKER` cashtags and uppercase symbols (with a blocklist for false positives)
- Counts mentions in the last 48h and compares to the prior 48h for momentum
- Sentiment uses keyword scoring (`calls`, `puts`, `moon`, etc.) on text containing each ticker

## Deploy on Vercel (scheduled report + cached page)

Visitors see a **pre-generated** report. A cron job rebuilds it once per day.

| Path | Purpose |
|------|---------|
| `/` or `/api/latest` | Serve the cached HTML report (fast) |
| `/api/cron` | Generate + save report (Vercel Cron only) |
| Cron `0 11 * * *` | Daily refresh at 11:00 UTC |

### 1. Create Vercel Blob storage

In the Vercel project → **Storage** → **Create Blob** → connect to the project.  
This sets `BLOB_READ_WRITE_TOKEN` automatically.

### 2. Environment variables

In **Settings → Environment Variables**:

| Variable | Required |
|----------|----------|
| `BLOB_READ_WRITE_TOKEN` | Yes (from Blob store) |
| `CRON_SECRET` | Yes (random string; Vercel Cron sends this) |
| `REDDIT_USER_AGENT` | Yes |
| `GEMINI_API_KEY` | If using Gemini |
| Others | Same as `.env.example` |

### 3. Deploy

```bash
vercel --prod
```

### 4. First report

Trigger once manually (use the same `CRON_SECRET` as in Vercel):

```bash
curl -H "Authorization: Bearer YOUR_CRON_SECRET" \
  "https://your-app.vercel.app/api/cron"
```

Then open `https://your-app.vercel.app/` — everyone sees that cached report until the next cron run.

### Vercel notes

- **Cron** requires [Vercel Pro](https://vercel.com/docs/cron-jobs) on your team.
- Set **Max Duration** to 300s (Pro) under Functions — Reddit + Gemini can take several minutes.
- Locally (no Blob token), reports cache to `data/reports/latest.html` instead.

## Raspberry Pi cron (daily)

```cron
0 6 * * * cd /home/pi/WSBStockMonitor && /home/pi/WSBStockMonitor/.venv/bin/python -m wsb_monitor --reddit-only >> /home/pi/WSBStockMonitor/logs/cron.log 2>&1
```

Use `--reddit-only` on the Pi for reliable counts without Gemini API usage.

## Project layout

```
wsb_monitor/
  __main__.py
  config.py
  report.py
  reddit/
    collector.py       # Routes public vs OAuth
    public_source.py # No API key
    praw_source.py     # OAuth via PRAW
    tickers.py     # Ticker extraction
    sentiment.py   # Keyword sentiment
  client/
    gemini.py
  runner.py        # Shared pipeline (CLI + Vercel)
api/
  index.py         # FastAPI app (Vercel entrypoint)
public/
  index.html       # Vercel landing page
vercel.json
```

# Trending Topics Fetcher

Pulls the **latest trending search topics** from Google Trends and writes the
**top results as JSON** — built to feed an AI video-creation pipeline (pick a hot
topic, then generate a video about it).

- **Source:** Google Trends "Trending Now" (the site's own internal API) — **no API key required**.
- **Window:** last 2–4 days (configurable; default 4).
- **Output:** JSON, top 30 by default.
- **Region:** India (`IN`) by default; any region code works.
- **Dependencies:** none — pure Python standard library (Python 3.10+).

## Quick start

```bash
python3 trending.py
```

This writes the top 30 Indian trends from the last 4 days to a date-stamped file
like `output/trending-2026-06-20.json` (one file per run/day).

## Usage

```bash
python3 trending.py [--geo IN] [--days 4] [--top 30] [--output output/trending-{date}.json]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--geo` | `IN` | Region code (`IN`, `US`, `GB`, …) |
| `--days` | `4` | Look-back window in days (2–4 recommended) |
| `--top` | `30` | Max number of results |
| `--output` | `output/trending-{date}.json` | Output file, or `-` to print to stdout. The `{date}` token is replaced with the current UTC date (`YYYY-MM-DD`). |

## Automation

A scheduled agent runs this fetcher **every two days** and commits the fresh
date-stamped JSON, so `output/` builds up a dated history of trending topics
with no manual runs.

### ✅ GitHub Actions workflow

A scheduled **GitHub Actions** workflow ([.github/workflows/trending.yml](.github/workflows/trending.yml))
runs the fetcher on a cron schedule — no local machine required.

| Setting | Value |
|---------|-------|
| Schedule | `30 18 */2 * *` → **12:00 AM IST**, every 2nd day |
| Runner | `ubuntu-latest` (open outbound internet) |
| Auth | built-in `GITHUB_TOKEN` (no PAT or integration) |

On each run the workflow checks out the repo, runs `python3 trending.py`, then
**commits & pushes** the new `output/trending-YYYY-MM-DD.json` back to `main` —
accumulating a dated history in the repo. It won't commit a failed/empty run;
instead it **opens (or comments on) a GitHub issue** titled
`Trending fetch failed — <date>` with the exit code and full error output.

> **Why not a Claude cloud routine?** The Claude Code cloud sandbox routes
> outbound traffic through an egress proxy that blocks `trends.google.com`
> (the fetch fails with `Tunnel connection failed: 403 Forbidden`). GitHub's
> runners have open internet, so the job lives here instead.

> **Note on "every two days":** cron's `*/2` on day-of-month resets at month
> boundaries, so the gap between the 31st and the 1st is one day rather than two
> — the standard cron approximation.

You can also trigger it manually from the repo's **Actions** tab
("Run workflow").

### 🧹 Weekly cleanup workflow

A second **GitHub Actions** workflow ([.github/workflows/Sunday_delete.yml](.github/workflows/Sunday_delete.yml))
prunes the accumulated history so `output/` keeps only the latest snapshot.

| Setting | Value |
|---------|-------|
| Schedule | `20 18 * * 0` → **every Sunday 23:50 IST** (18:20 UTC) |
| Runner | `ubuntu-latest` |
| Auth | built-in `GITHUB_TOKEN` |

On each run it keeps only the newest `output/trending-*.json` (the filenames are
date-stamped, so they sort chronologically) and **deletes every other JSON file
in `output/`**, committing the removal back to `main`. If there's only one file
(or none), it does nothing. It can also be triggered manually from the
**Actions** tab.

Examples:

```bash
python3 trending.py --days 2 --top 10        # last 2 days, top 10
python3 trending.py --geo US --output -      # US trends, print to stdout
```

## Output format

```json
{
  "source": "Google Trends - Trending Now",
  "region": "IN",
  "generated_at": "2026-06-20T08:00:00+00:00",
  "window_days": 4,
  "count": 30,
  "results": [
    {
      "rank": 1,
      "topic": "brazil score",
      "approx_traffic": 2000,
      "started_at": "2026-06-20T01:30:00+00:00",
      "related_queries": ["brazil haiti", "brazil live", "..."],
      "news": [
        {
          "title": "Brazil vs. Haiti LIVE: World Cup 2026 updates",
          "url": "https://www.espn.in/football/story/...",
          "source": "ESPN India",
          "published_at": "2026-06-20T00:50:00+00:00",
          "picture": "https://encrypted-tbn3.gstatic.com/images?q=..."
        }
      ]
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `topic` | The trending search term |
| `approx_traffic` | Approximate search volume (used for ranking) |
| `started_at` | When the topic started trending (UTC) |
| `related_queries` | Related search terms |
| `news` | News articles driving the trend |

## Notes

- The number of available trends depends on what Google is surfacing for the
  region/window; if fewer than `--top` exist, you get what's available.
- This uses an undocumented Google endpoint, so the response shape can change
  over time. The parser fails loudly (non-zero exit + stderr message) rather
  than emitting malformed JSON.

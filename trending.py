#!/usr/bin/env python3
"""Pull the latest trending search topics from Google Trends and emit JSON.

Data source: Google Trends "Trending Now" endpoint (the same internal API the
trends.google.com site uses) -- no API key required. It supports an hours
look-back, so we can scope results to the last 2-4 days and return up to ~30+
topics, each with its approximate search volume, when it started trending,
related queries, and the news articles driving it.

Examples:
    python trending.py                 # India, last 4 days, top 30 -> output/trending-YYYY-MM-DD.json
    python trending.py --days 2 --top 10
    python trending.py --geo US --output -   # print to stdout only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

BATCH_URL = "https://trends.google.com/_/TrendsUi/data/batchexecute"
RPC_ID = "i0OFE"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) trending-fetcher/1.0"


def fetch_trends(geo: str, hours: int, lang: str = "en", timeout: int = 30) -> list:
    """Call the Trending Now batchexecute endpoint and return the raw trend list."""
    rpc_payload = f'[null,null,"{geo}",{hours},"{lang}",1]'
    f_req = json.dumps([[[RPC_ID, rpc_payload]]])
    body = "f.req=" + quote(f_req)

    req = Request(
        BATCH_URL,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")

    # Response is prefixed with the XSSI guard line )]}'
    newline = text.index("\n")
    outer = json.loads(text[newline + 1 :])
    # An unknown/empty region yields a row with no payload at index 2.
    payload = outer[0][2] if outer and len(outer[0]) > 2 else None
    if not payload:
        return []
    inner = json.loads(payload)
    return inner[1] or []


def _ts_to_iso(ts_field) -> str | None:
    """Trends timestamps arrive as [unix_seconds]. Convert to ISO 8601 (UTC)."""
    if not ts_field:
        return None
    try:
        return datetime.fromtimestamp(ts_field[0], tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_news(raw_news) -> list[dict]:
    """Each news item is [title, url, source, [ts], picture]."""
    news = []
    for n in raw_news or []:
        news.append(
            {
                "title": n[0] if len(n) > 0 else None,
                "url": n[1] if len(n) > 1 else None,
                "source": n[2] if len(n) > 2 else None,
                "published_at": _ts_to_iso(n[3]) if len(n) > 3 else None,
                "picture": n[4] if len(n) > 4 else None,
            }
        )
    return news


def normalize(raw_trends: list) -> list[dict]:
    """Turn raw trend records into clean dicts.

    Record layout: [0]=topic, [1]=news, [3]=[start_ts], [6]=traffic, [9]=related.
    """
    out = []
    for t in raw_trends:
        out.append(
            {
                "topic": t[0] if len(t) > 0 else None,
                "approx_traffic": t[6] if len(t) > 6 and isinstance(t[6], int) else 0,
                "started_at": _ts_to_iso(t[3]) if len(t) > 3 else None,
                "related_queries": (t[9] if len(t) > 9 and t[9] else []),
                "news": parse_news(t[1]) if len(t) > 1 else [],
            }
        )
    return out


def build_report(trends: list[dict], geo: str, days: int, top: int) -> dict:
    """Sort by search volume, keep the top N, and attach metadata."""
    trends.sort(key=lambda x: x["approx_traffic"], reverse=True)
    results = [{"rank": i, **t} for i, t in enumerate(trends[:top], start=1)]
    return {
        "source": "Google Trends - Trending Now",
        "region": geo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "count": len(results),
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--geo", default="IN", help="Region code, e.g. IN, US, GB (default: IN)")
    p.add_argument(
        "--days", type=int, default=4, help="Look-back window in days, 2-4 recommended (default: 4)"
    )
    p.add_argument("--top", type=int, default=30, help="Max number of results (default: 30)")
    p.add_argument(
        "--output",
        default="output/trending-{date}.json",
        help=(
            "Output JSON file path, or '-' for stdout only. The token '{date}' is "
            "replaced with the current UTC date (YYYY-MM-DD). "
            "(default: output/trending-{date}.json)"
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        raw = fetch_trends(args.geo, hours=args.days * 24)
    except Exception as exc:  # noqa: BLE001 - surface any network/parse failure clearly
        print(f"error: failed to fetch Google Trends data: {exc}", file=sys.stderr)
        return 1

    trends = normalize(raw)
    report = build_report(trends, geo=args.geo, days=args.days, top=args.top)
    payload = json.dumps(report, indent=2, ensure_ascii=False)

    if args.output != "-":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = Path(args.output.replace("{date}", today))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {report['count']} trends to {out_path}", file=sys.stderr)
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

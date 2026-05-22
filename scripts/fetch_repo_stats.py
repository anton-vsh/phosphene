#!/usr/bin/env python3
"""Fetch GitHub repo stats and append a daily snapshot to docs/stats-data.jsonl.

Runs from .github/workflows/repo-stats.yml on a 24h cron. The GitHub Action
default token has push access to the repo it runs in, which is exactly what
the Traffic API (/repos/:owner/:repo/traffic/*) requires.

Why a custom script (not the off-the-shelf `github-repo-stats` Action):
- Mr Bizarro asked for "stable, has historic data, basic stuff" — keep the
  surface tiny and readable top-to-bottom.
- No build step, no node, no docker. Just stdlib urllib.
- Schema lives next to us; we can add fields later without renegotiating
  with an upstream marketplace action.

Output schema (one JSON object per UTC day, newline-delimited):

    {
      "date":   "2026-05-22",          # UTC YYYY-MM-DD (the day fetched)
      "fetched_at": "...Z",            # full ISO timestamp
      "clones": {"count": N, "uniques": N},      # daily-window slice
      "views":  {"count": N, "uniques": N},
      "stars":         N,                         # total today
      "forks":         N,
      "open_issues":   N,
      "open_prs":      N,
      "watchers":      N,
      "subscribers":   N,                         # actual GitHub watch
      "referrers": [{"referrer": "...", "count": N, "uniques": N}, ...],
      "paths":     [{"path": "...", "count": N, "uniques": N, "title": "..."}, ...]
    }

The clones/views counts here are the SUM of the latest 24 hours of the
Traffic API's 15-day day-array. The full 15-day curve from the API rotates
out by tomorrow, so the only way to retain it is to snapshot daily and
append. The dashboard reads the JSONL append-only.

Idempotent: if today's date already has an entry, the new fetch REPLACES
it (so re-runs in the same UTC day don't duplicate rows).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---- config --------------------------------------------------------------

REPO = os.environ.get("PHOSPHENE_REPO", "mrbizarro/phosphene")
TOKEN = (
    os.environ.get("GH_STATS_TOKEN")  # explicit override
    or os.environ.get("GITHUB_TOKEN")  # default in GH Actions
    or ""
).strip()
OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "stats-data.jsonl"

API = "https://api.github.com"
UA = "phosphene-repo-stats/1"

if not TOKEN:
    sys.stderr.write(
        "ERROR: no GitHub token. Set GH_STATS_TOKEN or run inside GitHub "
        "Actions (which injects GITHUB_TOKEN automatically).\n"
    )
    sys.exit(1)

# ---- http helpers --------------------------------------------------------


def _get(path: str, accept: str = "application/vnd.github+json") -> dict | list:
    """GET an API path. Raises on non-2xx so the Action surfaces failures."""
    url = path if path.startswith("http") else f"{API}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": accept,
            "User-Agent": UA,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"HTTP {exc.code} on {url}: {body[:300]}\n")
        raise


def _get_paginated(path: str, accept: str = "application/vnd.github+json") -> list:
    """Drain ?per_page=100 pages. Used for stargazers timeline."""
    out: list = []
    page = 1
    sep = "&" if "?" in path else "?"
    while True:
        chunk = _get(f"{path}{sep}per_page=100&page={page}", accept=accept)
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
        if page > 200:  # safety — 20k stars is enough
            break
    return out


# ---- metric fetchers -----------------------------------------------------


def fetch_repo() -> dict:
    """The repo object — covers stars/forks/issues/watchers."""
    r = _get(f"/repos/{REPO}")
    return {
        "stars":       int(r.get("stargazers_count", 0)),
        "forks":       int(r.get("forks_count", 0)),
        "open_issues": int(r.get("open_issues_count", 0)),  # includes PRs
        "watchers":    int(r.get("watchers_count", 0)),     # alias for stars
        "subscribers": int(r.get("subscribers_count", 0)),  # actual "watch"
    }


def fetch_open_prs() -> int:
    """The repo's open_issues_count includes PRs. Disambiguate so the
    dashboard can show issues and PRs separately."""
    # /search counts are cheap and don't paginate full result lists.
    q = f"repo:{REPO}+is:pr+is:open"
    r = _get(f"/search/issues?q={q}")
    return int(r.get("total_count", 0))


def fetch_clones() -> tuple[int, int]:
    """Last 24 hours of clones (the most recent entry in the 15-day array).
    Returns (count, uniques) for the most-recent day so we can graph day-
    over-day. Older entries get permanently archived in previous JSONL
    rows."""
    r = _get(f"/repos/{REPO}/traffic/clones")
    days = r.get("clones") or []
    if not days:
        return 0, 0
    today = days[-1]
    return int(today.get("count", 0)), int(today.get("uniques", 0))


def fetch_views() -> tuple[int, int]:
    """Last 24h of repo page views — same shape as clones."""
    r = _get(f"/repos/{REPO}/traffic/views")
    days = r.get("views") or []
    if not days:
        return 0, 0
    today = days[-1]
    return int(today.get("count", 0)), int(today.get("uniques", 0))


def fetch_referrers() -> list[dict]:
    """Top 10 referring domains over the rolling 14-day window. We snapshot
    the 14d aggregate every day rather than try to derive a per-day
    breakdown (the API doesn't give one)."""
    r = _get(f"/repos/{REPO}/traffic/popular/referrers")
    if not isinstance(r, list):
        return []
    return [
        {
            "referrer": x.get("referrer", "?"),
            "count":    int(x.get("count", 0)),
            "uniques":  int(x.get("uniques", 0)),
        }
        for x in r[:10]
    ]


def fetch_paths() -> list[dict]:
    """Top 10 paths viewed over the rolling 14d. Tells us which docs are
    actually getting read (README vs STATE vs ROADMAP, etc)."""
    r = _get(f"/repos/{REPO}/traffic/popular/paths")
    if not isinstance(r, list):
        return []
    return [
        {
            "path":    x.get("path", "?"),
            "title":   (x.get("title", "") or "")[:120],
            "count":   int(x.get("count", 0)),
            "uniques": int(x.get("uniques", 0)),
        }
        for x in r[:10]
    ]


def fetch_release_downloads() -> dict:
    """Cumulative downloads per release asset. GitHub provides no time
    series here, so we just take a snapshot — the dashboard can derive
    deltas across snapshots itself. Empty when the repo has no releases
    (Phosphene currently ships via Pinokio clone, not release binaries)."""
    try:
        rs = _get(f"/repos/{REPO}/releases?per_page=100")
        if not isinstance(rs, list):
            return {}
    except urllib.error.HTTPError:
        return {}
    total = 0
    per_release: dict = {}
    for rel in rs:
        tag = rel.get("tag_name", "?")
        rel_total = 0
        for a in rel.get("assets") or []:
            n = int(a.get("download_count", 0))
            rel_total += n
            total += n
        per_release[tag] = rel_total
    return {"total": total, "by_release": per_release}


# ---- main ----------------------------------------------------------------


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    iso_now = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{iso_now}] fetching stats for {REPO}", flush=True)

    repo = fetch_repo()
    print(f"  repo: {repo}", flush=True)
    open_prs = fetch_open_prs()
    repo["open_prs"] = open_prs
    # open_issues from the repo API includes PRs — subtract to disambiguate.
    repo["open_issues"] = max(0, repo["open_issues"] - open_prs)
    print(f"  prs: {open_prs} (open_issues adjusted to {repo['open_issues']})", flush=True)

    clones_count, clones_uniques = fetch_clones()
    views_count, views_uniques = fetch_views()
    print(f"  clones today: {clones_count} ({clones_uniques} unique)", flush=True)
    print(f"  views today:  {views_count} ({views_uniques} unique)", flush=True)

    referrers = fetch_referrers()
    paths = fetch_paths()
    releases = fetch_release_downloads()
    print(f"  referrers: {len(referrers)}  paths: {len(paths)}  "
          f"release downloads total: {releases.get('total', 0)}", flush=True)

    row = {
        "date": today,
        "fetched_at": iso_now,
        **repo,
        "clones": {"count": clones_count, "uniques": clones_uniques},
        "views":  {"count": views_count,  "uniques": views_uniques},
        "referrers": referrers,
        "paths":     paths,
        "releases":  releases,
    }

    # Idempotent append: replace today's row if it already exists.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if OUTPUT.exists():
        for line in OUTPUT.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("date") == today:
                    continue  # drop today's prior row
                existing.append(obj)
            except json.JSONDecodeError:
                continue
    existing.append(row)
    OUTPUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in existing) + "\n",
        encoding="utf-8",
    )
    print(f"  wrote {len(existing)} rows → {OUTPUT.relative_to(OUTPUT.parent.parent)}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

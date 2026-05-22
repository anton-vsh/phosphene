# Phosphene repo stats — maintainer guide

A tiny, stdlib-only pipeline that snapshots GitHub repo metrics every day at
03:17 UTC and publishes a static dashboard via GitHub Pages. Live dashboard:
**https://mrbizarro.github.io/phosphene/stats.html** (served from `main`
`/docs`). Nothing here calls a paid service or phones home from end-user
machines — the whole stack is three files you can read in five minutes.

## The three components

| File | Role |
|---|---|
| `scripts/fetch_repo_stats.py` | Fetcher. Hits GitHub's REST API, builds one JSON row per UTC day. Pure stdlib (`urllib`). |
| `docs/stats-data.jsonl` | Store. Append-only, newline-delimited JSON. Lives in git so history survives the Traffic API's 15-day rolling window. |
| `docs/stats.html` | Dashboard. Loads the JSONL at page load, renders charts client-side. No build step. |

Glue: `.github/workflows/repo-stats.yml` runs the fetcher daily, commits the
updated JSONL, and opens an issue if anything breaks.

## Run it locally

```bash
GITHUB_TOKEN=$(gh auth token) python3 scripts/fetch_repo_stats.py
```

Idempotent — re-running on the same UTC day replaces today's row. Flags:

```bash
python3 scripts/fetch_repo_stats.py --dry-run             # don't write JSONL
python3 scripts/fetch_repo_stats.py --repo OWNER/NAME     # different repo
```

Both flags are also exposed from **Actions → repo-stats → Run workflow**.

## Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch**, Branch: `main`, folder
`/docs`. Dashboard appears at `https://<owner>.github.io/<repo>/stats.html`
within a minute.

## Add a new metric

1. **`scripts/fetch_repo_stats.py`** — add a fetcher function, add the key
   to the row dict in `main()`, update the schema comment at the top.
2. **`docs/stats.html`** — read the new key per row and render it. Plain JS
   `fetch()` on the JSONL, no build.

Old rows won't have the key, so default missing values (`?? 0` in JS,
`row.get(key, 0)` in Python). Then run `workflow_dispatch` with
`dry_run: true` to verify the fetcher still works before committing.

## How to interpret the data

- **clones** — every `git clone`, including CI and bots. Pinokio installs
  Phosphene by `git clone`, so **a Pinokio install looks identical to a
  human running `git clone`**. Don't read clones as "humans who installed."
- **views** — github.com page views. Cached aggressively at the edge — a
  real visitor may not show up for hours.
- **referrers** — top 10 over a 14-day rolling window, no per-day
  breakdown. Direct nav, dark-social (DMs / Slack / email), and most mobile
  clients show up as "Google" or empty. Twitter / Discord / Reddit traffic
  arriving without a `Referer` header **won't appear here**.
- **paths** — top 10 most-viewed paths over the same 14-day window. Same
  caveats as referrers.
- **stars / forks / open_issues / open_prs / subscribers** — point-in-time
  totals. `subscribers` is the real "Watch" count; `watchers` is a legacy
  alias for stars.
- **releases.by_release** — cumulative downloads per asset. Phosphene ships
  through Pinokio, so this is usually empty.

## FAQ

**Why no client telemetry?** Mr Bizarro has explicitly chosen public-only
metrics. No analytics SDK in the Pinokio app, no phone-home, no third-party
JS in the dashboard. Everything here is what GitHub already shows in the
Insights tab — we're just preserving it past the 15-day window.

**Why public data?** The whole stack stays inside `github.com` and the repo
itself. No secrets beyond the default `GITHUB_TOKEN`, no external services
to lock us out, no separate dashboard host to forget about and rot.

**How long does data live?** Forever — every snapshot is a git commit. To
prune, edit `docs/stats-data.jsonl` directly and commit. There's no DB.

## Troubleshooting

- **Action failing** → check Issues filtered by `stats-broken`. The
  workflow auto-opens one issue per outage and comments on it for each
  subsequent failure (so a 7-day outage = 1 issue + 6 comments).
- **Workflow missing from Actions tab** → you pushed without the `workflow`
  OAuth scope. Run `gh auth refresh -s workflow` and push the
  `.github/workflows/repo-stats.yml` file again from a local clone.
- **Dashboard blank** → check `docs/stats-data.jsonl` actually has rows.
  If empty, run the fetcher locally and commit. If full, open devtools —
  `fetch()` 404s mean Pages isn't pointed at `/docs` on `main`.

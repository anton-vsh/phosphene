# Phosphene anonymous telemetry

## TL;DR

- **OFF by default.** Enable it in **Settings → Anonymous analytics**.
- Sends a small JSON event per render boundary. No prompts. No image
  bytes. No filenames. No paths. No hostname. No IP-in-payload.
- A single anonymous install id (32-char hex) is generated the first
  time you opt in. Click **forget me** to rotate it.
- All HTTP is non-blocking and best-effort. A flaky endpoint will never
  stall a render.
- Endpoint configurable via `PHOSPHENE_ANALYTICS_ENDPOINT` env var.
  Default: `https://analytics.phosphene.ai/v1/event` (run by Mr Bizarro).

## Why

Phosphene is a young open-source project. GitHub release-download stats
only show a 14-day window, and Pinokio installs aren't counted at all.
Without **opt-in** telemetry we have no way to tell:

- which Apple Silicon tiers people actually run on (M2, M3, M4 Max,
  Ultra…) so we can prioritize the right perf wins;
- which modes (T2V, I2V, A2V, FFLF, Extend, Character) get used most
  vs. which are gathering dust;
- what's breaking in the field — OOMs, missing models, helper crashes,
  bad LoRA combos — so we can ship fixes rather than wait for an issue
  to land;
- whether a release regressed render time on real hardware.

If you'd rather not share any of this, leave the toggle OFF — Phosphene
works identically. We mean it.

## What we collect

Every event carries:

| Field         | Example              | Notes                                    |
|---------------|----------------------|------------------------------------------|
| `event`       | `render_done`        | The event type — see list below.         |
| `ts`          | `2026-05-21T19:42:11Z` | ISO 8601 UTC, second precision.        |
| `install_id`  | `a1b2c3…`            | Anonymous 32-char hex. Generated locally on first opt-in; you can rotate it. |

Plus, **per event type**:

### `panel_boot` — fires once at panel startup

| Field           | Example                | Why                                  |
|-----------------|------------------------|--------------------------------------|
| `version`       | `0.10.3`               | Phosphene release tag if known.      |
| `sha`           | `ec1437f`              | Short commit if you're on dev.       |
| `branch`        | `dev`                  | `main` or `dev`.                     |
| `tier`          | `M4 Max 64 GB`         | Hardware tier label.                 |
| `allows_q8`     | `true`                 | Whether the machine can run Q8 HQ.   |
| `os`            | `macOS 26.4`           | OS family + major.minor only.        |
| `machine`       | `arm64`                | CPU architecture.                    |
| `python`        | `3.11`                 | Major.minor.                         |
| `ram_gb_bucket` | `64`                   | Snapped to nearest bucket (16/32/48/64/96/128/192/256). Raw GB would near-uniquely identify users. |
| `cpu_brand`     | `Apple M4 Max`         | Truncated to 64 chars.               |

### `render_start` / `render_done` / `render_failed` / `render_cancelled`

| Field            | Example       | Notes                                       |
|------------------|---------------|---------------------------------------------|
| `mode`           | `i2v`         | One of: t2v, i2v, a2v, character, fflf, extend, image, audio. |
| `quality`        | `q8_hq`       | Pipeline tier picked.                       |
| `width`          | `1280`        | Output width in pixels.                     |
| `height`         | `704`         | Output height.                              |
| `frames`         | `97`          | Frame count requested.                      |
| `has_character`  | `true`        | Whether a Phosphene character LoRA is loaded — not which one. |
| `lora_count`     | `2`           | Number of user LoRAs (count only, no names).|
| `hdr`            | `false`       | HDR IC-LoRA pipeline?                       |
| `enhance`        | `true`        | Gemma prompt-enhance step run?              |
| `upscale`        | `false`       | Post-upscale step run?                      |
| `accel`          | `exact`       | Fast / Exact pill.                          |
| `engine`         | `mlx`         | Pipeline engine (mlx / comfy).              |
| `elapsed_sec`    | `306.5`       | End-to-end seconds. Only on `_done`/`_failed`/`_cancelled`. |
| `error_category` | `oom`         | Only on `_failed`. Coarse bucket — see list below. |

Error categories: `oom`, `hf_auth`, `hf_gated`, `wrong_backend`,
`missing_model`, `q8_missing`, `missing_deps`, `character_error`,
`file_missing`, `helper_pipe`, `runtime`.

### `helper_crash` — fires when the helper subprocess exits unexpectedly

| Field           | Example      | Notes                                  |
|-----------------|--------------|----------------------------------------|
| `exit_code`     | `-9`         | OS exit code.                          |
| `last_action`   | `generate`   | What the helper was doing.             |
| `mode`          | `i2v`        | Same shape as above.                   |

### `settings_opt_in` / `settings_opt_out`

| Field     | Example | Notes                                       |
|-----------|---------|---------------------------------------------|
| `version` | `0.10.3`| Phosphene release tag at the moment of the flip. |

`settings_opt_out` is the **last event** sent before silence. After
that we send nothing until you opt in again.

## What we **never** collect

The wire sanitizer drops any field with these keys, even if a caller
accidentally tries to attach one:

```
prompt, negative_prompt, image, image_path, audio_path,
output, output_path, path, filename,
hostname, username, user
```

Beyond that:

- **No URL parameters** — events are POSTed as JSON bodies.
- **No IP in payload** — your IP is visible to the receiving server at
  the TCP layer (same as any HTTP request) but it's not stored or
  attached to the install_id.
- **No reference image bytes / no rendered frames / no audio.**
- **No GitHub username, no machine name, no email, no API tokens.**
- **No LoRA filenames** — we only count how many you used.

## Defense in depth

Even if a future code change tried to ship more data than the schema
above, `analytics.py` enforces hard limits:

- **4 KB max payload.** Anything over gets dropped, not truncated.
- **200-char max per string value.** Runaway error strings get cut.
- **512-event in-memory queue.** When the endpoint is unreachable,
  oldest events drop first — never unbounded growth.
- **4 s socket timeout.** A flaky endpoint can't stall a render.
- **Daemon thread.** The flusher dies with the process; it never holds
  shutdown open.

The full implementation lives in `analytics.py` — 350 lines, readable
top-to-bottom in under 10 minutes. Audit before you opt in.

## Controlling it

### Opt in / opt out

**Settings → Anonymous analytics → Enable / Disable.**

Takes effect immediately. No restart, no helper kick.

### Rotate your anonymous id ("forget me")

**Settings → Anonymous analytics → forget me** (button next to the id).

Generates a fresh 32-char hex. Past events from your old id stay in
the receiver's logs but can no longer be correlated to your new
events.

### Self-host the endpoint

Set `PHOSPHENE_ANALYTICS_ENDPOINT` in the panel's environment:

```bash
export PHOSPHENE_ANALYTICS_ENDPOINT="https://my-receiver.example.com/event"
```

If both the env var and the saved endpoint are unset, telemetry is a
no-op even when the toggle is ON (fail-safe for forks).

### Disable entirely at build time

Leave the toggle OFF. Done. The code path is a no-op — `emit()` short-
circuits inside `Analytics.emit` when `is_enabled()` returns False.

## Receiver

The default endpoint at `analytics.phosphene.ai` accepts POST JSON,
returns `204 No Content`, retains events for 90 days, and drops any
field outside the schema above on ingest. Source for the receiver is
not yet public — happy to publish it once the schema stabilizes. File
an issue if you'd like to see it sooner.

## Questions?

Open an issue at <https://github.com/mrbizarro/phosphene/issues> with
the `telemetry` label. The privacy posture is intentionally
conservative — if any of it makes you uncomfortable, please tell us so
we can fix it.

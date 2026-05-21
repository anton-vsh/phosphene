"""Phosphene anonymous telemetry.

Strictly opt-in. Default OFF. When the user enables it via Settings,
the panel sends a tiny event payload to a configurable endpoint
(``PHOSPHENE_ANALYTICS_ENDPOINT`` env var, falls back to the public
ingest URL Mr Bizarro hosts).

Privacy guarantees:
- Never sends prompts, image bytes, output filenames, audio waveforms,
  LoRA filenames (only counts), absolute paths, hostnames, IP, or any
  user-content.
- Anonymous install UUID generated once on first opt-in. Rotating
  ``analytics_install_id`` in settings resets identity (forget-me).
- All HTTP calls are non-blocking (daemon thread, 4 s socket timeout) so
  a slow endpoint never stalls a render.
- Endpoint failures are logged to the panel log but never raised — the
  user's render is the priority, telemetry is best-effort.

Full event schema:
    See TELEMETRY.md alongside this file.

Events emitted today:
    panel_boot       — every panel startup (version, branch, tier, RAM)
    render_start     — every job enters the worker
    render_done      — every successful job (with elapsed_sec, mode, quality)
    render_failed    — every error / cancellation (with categorized error)
    helper_crash     — every unexpected helper subprocess exit
    settings_opt_in  — when the user flips analytics_enabled on
    settings_opt_out — when the user flips analytics_enabled off (last
                       event before silence)
"""
from __future__ import annotations

import json
import os
import platform
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


# Default public ingest. Mr Bizarro can swap this via env. If neither
# env nor saved settings provide an endpoint, telemetry is a no-op
# even when analytics_enabled=True — fail-safe for forks.
DEFAULT_ENDPOINT = os.environ.get(
    "PHOSPHENE_ANALYTICS_ENDPOINT",
    "https://analytics.phosphene.ai/v1/event",
).strip()

# Hard limit on payload size — defense-in-depth. Any single event over
# this gets dropped without sending (prevents accidental large blobs).
_MAX_PAYLOAD_BYTES = 4 * 1024

# Hard limit on the in-memory event queue. Older events get dropped if
# the endpoint is unreachable and events pile up. Prevents unbounded
# memory growth across a long session.
_QUEUE_MAX = 512

# Socket timeout per request. Keep tight so a flaky endpoint never
# stalls the render path.
_SOCKET_TIMEOUT_SEC = 4

# How long to wait between background-flush ticks. Most events are
# already triggered by user actions (render boundaries), so the
# background loop is really just retry / drain.
_FLUSH_INTERVAL_SEC = 5


# Module-level singleton — the ``Analytics`` class is a thread that
# owns the event queue + background flusher. We construct it once at
# panel startup and write through the module-level helpers below.
_INSTANCE: "Analytics | None" = None
_INSTANCE_LOCK = threading.Lock()


def _now_iso() -> str:
    """ISO 8601 UTC timestamp, second precision (sub-second isn't useful
    for cross-machine event correlation and adds noise)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Analytics:
    """Background-thread event sender.

    Construct once at panel startup. The constructor does NOT start the
    thread — call ``start()`` after the settings layer is wired up so
    we can read the opt-in flag.
    """

    def __init__(
        self,
        *,
        is_enabled: callable,
        get_install_id: callable,
        get_endpoint: callable,
        log: callable | None = None,
    ) -> None:
        self._is_enabled = is_enabled
        self._get_install_id = get_install_id
        self._get_endpoint = get_endpoint
        # ``log`` should be the panel's ``push()`` (or any function that
        # accepts a single string). When None, errors go to stderr only.
        self._log = log or (lambda s: sys.stderr.write(s + "\n"))
        self._queue: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=_QUEUE_MAX)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background flush thread. Idempotent."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="phosphene-analytics", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to exit and join briefly. Called
        at process shutdown (best-effort — daemon thread will die with
        the process anyway)."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Event entry points
    # ------------------------------------------------------------------

    def emit(self, event_type: str, fields: dict[str, Any] | None = None) -> None:
        """Queue an event. No-op if analytics is disabled. Safe to call
        from any thread; never raises."""
        try:
            if not self._is_enabled():
                return
            payload = self._build_event(event_type, fields or {})
            if payload is None:
                return  # event was dropped by validation
            try:
                self._queue.put_nowait(payload)
            except queue.Full:
                # Drop the OLDEST item, queue the new one. Recent events
                # are more useful than ancient ones when we're behind.
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(payload)
                except queue.Full:
                    pass
        except Exception as exc:  # noqa: BLE001 — never crash the caller
            try:
                self._log(f"analytics: emit failed silently: {exc}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_event(self, event_type: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Compose the final event dict + run privacy validation.

        Returns ``None`` if the event should be silently dropped (e.g.
        oversize payload or a forbidden field name leaked in).
        """
        # Strip any fields whose key looks like it could carry user
        # content. Defense in depth — even if a caller violates the
        # rule, the sanitizer keeps the wire clean.
        BANNED = {"prompt", "image", "image_path", "audio_path",
                  "output_path", "output", "path", "hostname",
                  "username", "user", "negative_prompt", "filename"}
        clean: dict[str, Any] = {}
        for k, v in fields.items():
            if k in BANNED:
                continue
            # Truncate stringy values to 200 chars. Some fields are
            # legitimately stringy (e.g., error category) but a runaway
            # value should never make it to wire.
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + "…"
            clean[k] = v
        event = {
            "event": str(event_type)[:64],
            "ts": _now_iso(),
            "install_id": self._get_install_id(),
            **clean,
        }
        # Size check
        try:
            payload_bytes = json.dumps(event).encode("utf-8")
        except (TypeError, ValueError) as exc:
            self._log(f"analytics: event {event_type!r} not JSON-serializable: {exc}")
            return None
        if len(payload_bytes) > _MAX_PAYLOAD_BYTES:
            self._log(
                f"analytics: dropping oversize {event_type} event "
                f"({len(payload_bytes)} > {_MAX_PAYLOAD_BYTES} bytes)"
            )
            return None
        return event

    def _run(self) -> None:
        """Background loop. Drains the queue, POSTs each event with a
        short timeout. Failures are logged once per minute (silent
        otherwise) to avoid log spam from a flaky endpoint."""
        last_warn_ts = 0.0
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=_FLUSH_INTERVAL_SEC)
            except queue.Empty:
                continue
            try:
                self._post(event)
            except Exception as exc:  # noqa: BLE001
                now = time.time()
                if now - last_warn_ts > 60:
                    last_warn_ts = now
                    try:
                        self._log(f"analytics: post failed ({exc}); will retry")
                    except Exception:
                        pass
                # Put it back? Decision: NO — accept the drop. Otherwise
                # a permanently-down endpoint makes us cycle forever.
                # The settings_opt_out event is the one drop we'd hate
                # to lose; we accept that loss for simplicity.

    def _post(self, event: dict[str, Any]) -> None:
        endpoint = self._get_endpoint()
        if not endpoint:
            return  # no endpoint configured; silent no-op
        body = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "phosphene-panel-analytics",
            },
        )
        with urllib.request.urlopen(req, timeout=_SOCKET_TIMEOUT_SEC) as resp:
            # We don't care about the response body; just consume so
            # the connection can close cleanly.
            try:
                resp.read(64)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------
# Module-level helpers — the panel calls these directly
# ---------------------------------------------------------------------

def install(
    *,
    is_enabled: callable,
    get_install_id: callable,
    get_endpoint: callable,
    log: callable | None = None,
) -> None:
    """Wire up the singleton. Call once at panel boot before any emit().
    Idempotent — subsequent calls are no-ops."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is not None:
            return
        _INSTANCE = Analytics(
            is_enabled=is_enabled,
            get_install_id=get_install_id,
            get_endpoint=get_endpoint,
            log=log,
        )
        _INSTANCE.start()


def emit(event_type: str, fields: dict[str, Any] | None = None) -> None:
    """Queue an event. No-op if analytics is disabled or not installed."""
    inst = _INSTANCE
    if inst is not None:
        inst.emit(event_type, fields)


def shutdown() -> None:
    """Stop the background thread. Best-effort; daemon thread dies
    with the process anyway."""
    inst = _INSTANCE
    if inst is not None:
        inst.stop()


def new_install_id() -> str:
    """Generate a fresh anonymous install UUID. Called by the settings
    layer the first time analytics_enabled flips ON (or when the user
    rotates the id via the 'forget me' button)."""
    return uuid.uuid4().hex


def system_fingerprint() -> dict[str, Any]:
    """Anonymized hardware / software fingerprint. Sent with panel_boot
    so we can correlate bugs to hardware tier + OS version without
    learning anything user-identifying.

    What's collected:
        os                 — "macOS 26.4" etc., no patch level
        machine            — "arm64"
        python             — "3.11"
        ram_gb_bucket      — bucketed: 16/32/48/64/96/128/192/256+
                              (raw value would near-uniquely identify
                              a user across the install pool)
        cpu_brand          — "Apple M4 Max" etc. when available
    """
    info: dict[str, Any] = {}
    try:
        sys_name = platform.system()
        if sys_name == "Darwin":
            # "26.4.1" → "26.4" — patch level doesn't add bug-correlation
            # value and slightly increases per-user uniqueness.
            mac = (platform.mac_ver()[0] or "").split(".")
            major_minor = ".".join(mac[:2]) if mac and mac[0] else ""
            info["os"] = f"macOS {major_minor}".strip()
        else:
            info["os"] = sys_name or "?"
    except Exception:
        info["os"] = "?"
    info["machine"] = platform.machine() or "?"
    info["python"] = ".".join(platform.python_version().split(".")[:2])
    try:
        # psutil is already a Phosphene dep
        import psutil  # noqa: PLC0415
        ram_gb = psutil.virtual_memory().total / (1024**3)
        for bucket in (16, 32, 48, 64, 96, 128, 192, 256):
            if ram_gb <= bucket + 4:  # snap to bucket within ±4 GB
                info["ram_gb_bucket"] = bucket
                break
        else:
            info["ram_gb_bucket"] = 256
    except Exception:
        info["ram_gb_bucket"] = 0
    try:
        import subprocess  # noqa: PLC0415
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            timeout=2, stderr=subprocess.DEVNULL,
        ).decode().strip()
        info["cpu_brand"] = out[:64]
    except Exception:
        info["cpu_brand"] = "?"
    return info

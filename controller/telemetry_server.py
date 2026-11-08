"""Read-only telemetry endpoint for v91-core-system.

STANDARD LIBRARY ONLY - this module deliberately adds NO new runtime
dependencies (no FastAPI, no requests, no pyjwt).

Reality-first rules honored here:
- UNKNOWN is never reported as healthy ("unknown" != "ok").
- Read-only/advisory: this server never executes actions, never writes,
  and never claims state it was not given.
- DETECTION != AUTHORIZATION: exposing a metric grants no authority.
- Default bind address is 127.0.0.1 (local-only) unless the operator
  explicitly passes another host.
- Availability is proven by answering requests, never assumed.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable, Dict

UNKNOWN = "unknown"
OK = "ok"
FAILED = "failed"
DEGRADED = "degraded"

Snapshot = Dict[str, object]


def build_healthz(snapshot: Snapshot) -> Dict[str, object]:
    """Build the /healthz JSON document from caller-provided facts.

    checks: dict of name -> True/False/None. None (or any non-bool)
    means UNKNOWN and never aggregates to healthy.
    """
    checks = snapshot.get("checks")
    if not isinstance(checks, dict) or not checks:
        return {"status": UNKNOWN, "checks": {}, "reason": "no_checks_provided"}

    mapped: Dict[str, str] = {}
    for name, value in checks.items():
        if value is True:
            mapped[str(name)] = OK
        elif value is False:
            mapped[str(name)] = FAILED
        else:
            mapped[str(name)] = UNKNOWN

    values = list(mapped.values())
    if UNKNOWN in values:
        status, reason = UNKNOWN, "at_least_one_check_unknown"
    elif FAILED in values:
        status, reason = DEGRADED, "at_least_one_check_failed"
    else:
        status, reason = OK, "all_provided_checks_passed"

    result: Dict[str, object] = {"status": status, "checks": mapped, "reason": reason}
    gauges = snapshot.get("gauges")
    if isinstance(gauges, dict):
        result["gauges"] = {
            str(k): (v if isinstance(v, (int, float)) else UNKNOWN)
            for k, v in gauges.items()
        }
    return result


def _metric_name(name: object) -> str:
    """Sanitize a caller-provided name into a Prometheus-safe token."""
    safe = []
    for ch in str(name):
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        else:
            safe.append("_")
    token = "".join(safe)
    if not token or not (token[0].isalpha() or token[0] == "_"):
        token = "_" + token
    return token


def build_metrics(snapshot: Snapshot) -> str:
    """Build a Prometheus text-format (version 0.0.4) exposition."""
    lines = []
    gauges = snapshot.get("gauges")
    if isinstance(gauges, dict):
        for name, value in gauges.items():
            metric = _metric_name(name)
            if isinstance(value, bool):
                value = 1 if value else 0
            if isinstance(value, (int, float)):
                lines.append("v91_gauge_{0} {1}".format(metric, value))
            else:
                lines.append("# v91_gauge_{0} unknown".format(metric))
    checks = snapshot.get("checks")
    if isinstance(checks, dict):
        for name, value in checks.items():
            if value is True:
                state = 1
            elif value is False:
                state = 0
            else:
                state = -1  # UNKNOWN
            lines.append('v91_check{name="%s"} %d' % (_metric_name(name), state))
    return "\n".join(lines) + "\n"


def make_handler(snapshot_provider: Callable[[], Snapshot]) -> type:
    """Build an HTTP request handler class bound to a snapshot provider."""

    class TelemetryHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                body = json.dumps(build_healthz(snapshot_provider())).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/metrics":
                body = build_metrics(snapshot_provider()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            else:
                body = b"not found\n"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            # Read-only server: writes are refused, not ignored.
            body = b"read-only\n"
            self.send_response(405)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args) -> None:  # noqa: A002
            return  # keep CI logs quiet

    return TelemetryHandler


def serve(snapshot_provider: Callable[[], Snapshot], host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Create (but do not start) a telemetry server. Caller owns lifecycle."""
    return ThreadingHTTPServer((host, port), make_handler(snapshot_provider))

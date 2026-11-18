#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Hardened offline metrics exporter core (Issue #94).

Addresses the audit findings from the 2026-11-16 deployment draft:
- Missing, stale, non-finite or wrongly typed KPI values are reported
  as UNKNOWN/NO_DATA, never as 0 (zero is a measurement, not a gap).
- Chain integrity is only claimed from a real MeasurementStore chain
  verification; without the key the status is UNKNOWN, never VERIFIED.
- The exporter default bind address is loopback; binding to anything
  else requires an explicit, separate opt-in.
- HTML output escapes every value in its context; unparseable lines are
  counted and surfaced, never silently skipped.
- The report never derives claims (e.g. "physical test proven") from
  bare fields; unevidenced statements stay UNKNOWN.

Honest scope (SCRIPTED != INSTALLED):
- Pure functions plus a tiny render layer; no daemon, no network I/O,
  no systemd, no installation on a host. Deployment hardening items of
  Issue #94 that require a real host remain separate evidence levels.
"""

from __future__ import annotations

import html
import ipaddress
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from measurement_store import MeasurementStore, MeasurementStoreError

DEFAULT_BIND_ADDRESS = "127.0.0.1"
LOOPBACK_OPT_IN_HINT = (
    "binding outside loopback is refused by default; pass allow_non_loopback=True "
    "only after external exposure was explicitly configured and secured"
)


class MetricsExportError(RuntimeError):
    """Raised on fail-closed conditions: bad bind address, bad input."""


def validate_bind_address(address: Any = None, *, allow_non_loopback: bool = False) -> str:
    """Fail-closed bind address policy: loopback default, explicit opt-in for the rest."""
    if address is None:
        address = DEFAULT_BIND_ADDRESS
    if not isinstance(address, str) or not address.strip():
        raise MetricsExportError("bind address must be a non-empty string")
    candidate = address.strip()
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise MetricsExportError(f"bind address is not a valid IP literal: {candidate!r}") from exc
    if not parsed.is_loopback and not allow_non_loopback:
        raise MetricsExportError(LOOPBACK_OPT_IN_HINT)
    return candidate


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _usable_value(value: Any) -> bool:
    """A KPI value is usable only if numeric, non-bool and finite."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def read_ledger_entries(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read JSONL entries; unparseable lines are counted, never silently skipped."""
    path = Path(path)
    skipped = 0
    if not path.exists():
        return [], 0
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(entry, dict):
            skipped += 1
            continue
        entries.append(entry)
    return entries, skipped


def chain_integrity(path: Path) -> dict[str, Any]:
    """Chain status from the REAL store verification; UNKNOWN without key or on error."""
    path = Path(path)
    if not path.exists():
        return {"chain_verified": None, "reason": "ledger file missing", "entries": 0}
    entries, skipped = read_ledger_entries(path)
    if skipped:
        return {"chain_verified": False, "reason": "unparseable lines present", "entries": len(entries), "skipped_lines": skipped}
    try:
        store = MeasurementStore(path)
    except MeasurementStoreError:
        return {"chain_verified": None, "reason": "no usable store key; UNKNOWN, never VERIFIED", "entries": len(entries)}
    try:
        verified = store.verify_chain()
    except MeasurementStoreError:
        return {"chain_verified": None, "reason": "chain check failed; UNKNOWN, never VERIFIED", "entries": len(entries)}
    return {"chain_verified": verified, "reason": None if verified else "HMAC chain verification failed", "entries": len(entries)}


def resolve_kpis(
    entries: list[dict[str, Any]],
    *,
    now_utc: datetime | None = None,
    staleness_seconds: float = 900.0,
) -> dict[str, dict[str, Any]]:
    """Latest KPI per (sensor_id, metric): MEASURED or UNKNOWN, never a faked zero.

    Only MEASUREMENT_VALID records with usable values count. A sensor whose
    newest usable record is older than staleness_seconds is UNKNOWN.
    Quarantined records never contribute values.
    """
    if not isinstance(staleness_seconds, (int, float)) or isinstance(staleness_seconds, bool) or staleness_seconds <= 0:
        raise MetricsExportError("staleness_seconds must be a finite positive number")
    now = now_utc if now_utc is not None else datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise MetricsExportError("now_utc must be timezone-aware")
    now = now.astimezone(UTC)
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("record_type") != "MEASUREMENT_VALID":
            continue
        sensor = entry.get("sensor_id")
        metric = entry.get("metric")
        if not isinstance(sensor, str) or not sensor.strip() or not isinstance(metric, str) or not metric.strip():
            continue
        timestamp = _parse_utc(entry.get("source_time_utc"))
        if timestamp is None:
            continue
        key = (sensor, metric)
        current = latest.get(key)
        if current is None or timestamp > current["_timestamp"]:
            latest[key] = {"_timestamp": timestamp, "_entry": entry}
    result: dict[str, dict[str, Any]] = {}
    for (sensor, metric), item in latest.items():
        entry = item["_entry"]
        name = f"{sensor}.{metric}"
        if not _usable_value(entry.get("normalized_value")):
            result[name] = {"status": "UNKNOWN", "value": None,
                            "reason": "missing, non-finite or wrongly typed value is NO_DATA, not a measurement"}
            continue
        age = (now - item["_timestamp"]).total_seconds()
        if age > staleness_seconds:
            result[name] = {"status": "UNKNOWN", "value": None,
                            "reason": f"stale: newest usable record is {int(age)}s old (threshold {int(staleness_seconds)}s)"}
            continue
        if age < -staleness_seconds:
            result[name] = {"status": "UNKNOWN", "value": None,
                            "reason": "timestamp in the future; refusing to present it as fresh"}
            continue
        result[name] = {"status": "MEASURED", "value": float(entry["normalized_value"]),
                       "unit": entry.get("unit") if isinstance(entry.get("unit"), str) else None,
                       "source_time_utc": entry.get("source_time_utc")}
    return result


def render_prometheus(kpis: dict[str, dict[str, Any]]) -> str:
    """Prometheus exposition: measured values only; UNKNOWN is counted, never emitted as 0."""
    lines: list[str] = []
    unknown_total = 0
    for name in sorted(kpis):
        kpi = kpis[name]
        safe_name = name.replace(".", "_").replace(" ", "_")
        if kpi.get("status") != "MEASURED":
            unknown_total += 1
            lines.append(f'v91_kpi_unknown{{kpi="{html.escape(name, quote=True)}"}} 1')
            continue
        value = kpi.get("value")
        if not _usable_value(value):
            unknown_total += 1
            lines.append(f'v91_kpi_unknown{{kpi="{html.escape(name, quote=True)}"}} 1')
            continue
        lines.append(f"v91_kpi_value_{{{safe_name}}} {value!r}" if False else f"v91_kpi_value{{kpi=\"{html.escape(name, quote=True)}\"}} {float(value)!r}")
    lines.append(f"v91_kpi_unknown_total {unknown_total}")
    return "\n".join(lines) + "\n"


def render_html_report(
    *,
    title: str,
    kpis: dict[str, dict[str, Any]],
    chain: dict[str, Any],
    skipped_lines: int = 0,
    generated_at_utc: str | None = None,
) -> str:
    """HTML report with context-correct escaping and honest status rendering.

    No claim is derived from bare fields: chain status only from the verified
    flag, unevidenced aspects stay UNKNOWN, skipped lines are surfaced.
    """
    if not isinstance(title, str) or not title.strip():
        raise MetricsExportError("title must be a non-empty string")
    chain_verified = chain.get("chain_verified")
    if chain_verified is True:
        chain_line = "Kettenintegrität: VERIFIED (echte HMAC-Kettenprüfung über alle Einträge)"
    elif chain_verified is False:
        chain_line = "Kettenintegrität: FAILED (Kette konnte nicht vollständig verifiziert werden)"
    else:
        chain_line = "Kettenintegrität: UNKNOWN (kein Nachweis möglich; UNKNOWN wird nie als VERIFIED dargestellt)"
    entries = chain.get("entries", 0)
    skipped = int(skipped_lines or chain.get("skipped_lines") or 0)
    parts = [
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>",
        html.escape(title.strip()),
        "</title></head><body>",
        f"<h1>{html.escape(title.strip())}</h1>",
        f"<p>Erzeugt (UTC): {html.escape(generated_at_utc or 'UNKNOWN')}</p>",
        f"<p>{html.escape(chain_line)}</p>",
        f"<p>Ledger-Einträge (lesbar): {int(entries) if isinstance(entries, int) else 'UNKNOWN'}</p>",
        f"<p>Unlesbare Zeilen: {skipped}"
        + (" (werden gezählt und angezeigt, nie still übersprungen)" if skipped else "</p>"),
    ]
    if skipped:
        parts.append("</p>")
    parts.append("<h2>KPIs</h2><table border=\"1\"><tr><th>KPI</th><th>Status</th><th>Wert</th><th>Einheit</th><th>Begründung</th></tr>")
    if not kpis:
        parts.append("<tr><td colspan=\"5\">UNKNOWN: keine KPIs auflösbar (NO_DATA, nicht 0)</td></tr>")
    for name in sorted(kpis):
        kpi = kpis[name]
        value = kpi.get("value")
        shown = html.escape(repr(value)) if _usable_value(value) else "UNKNOWN"
        reason = kpi.get("reason")
        parts.append(
            "<tr><td>" + html.escape(name) + "</td><td>" + html.escape(str(kpi.get("status", "UNKNOWN")))
            + "</td><td>" + shown + "</td><td>" + html.escape(str(kpi.get("unit") or "UNKNOWN"))
            + "</td><td>" + html.escape(str(reason or "")) + "</td></tr>"
        )
    parts.append(
        "<p>Evidenzgrenze: Berichte belegen keine physischen Tests, keinen Hostbetrieb "
        "und keine Installation. Fehlende Evidenz bleibt UNKNOWN.</p>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)


def build_export(
    ledger_path: Path,
    *,
    now_utc: datetime | None = None,
    staleness_seconds: float = 900.0,
) -> dict[str, Any]:
    """One-shot snapshot: KPIs, chain status, skipped lines, Prometheus text."""
    entries, skipped = read_ledger_entries(Path(ledger_path))
    chain = chain_integrity(Path(ledger_path))
    kpis = resolve_kpis(entries, now_utc=now_utc, staleness_seconds=staleness_seconds)
    return {
        "kpis": kpis,
        "chain": chain,
        "skipped_lines": skipped,
        "prometheus": render_prometheus(kpis),
    }

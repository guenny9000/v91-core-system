"""Local autarky and resilience metrics (Issue #83).

Ehrliche, lokale Kennzahlen aus echten Messungen: UNKNOWN ist nie HEALTHY,
fehlende Quellen werden nie interpoliert. Keine Netzaufrufe, keine Wirkung
ueber den eigenen Rechner hinaus. SCRIPTED != INSTALLED.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence


class AutarkyMetricError(RuntimeError):
    """Metrics cannot be computed honestly."""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _parse_utc(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


class EnergyAutarky:
    """Self-sufficiency share from measured solar/grid/load intervals.

    A record counts only when solar_w AND grid_w are both measured non-negative
    numbers. Intervals with missing values are UNKNOWN and excluded, never
    interpolated. The result is UNKNOWN when no interval is measurable.
    """

    def __init__(self, records: Sequence[Mapping[str, object]]) -> None:
        if not isinstance(records, (list, tuple)):
            raise AutarkyMetricError("records must be a sequence of measurement dicts")
        self._records = list(records)

    def compute(self) -> dict:
        valid_solar = 0.0
        valid_grid = 0.0
        measured = 0
        unmeasured = 0
        for record in self._records:
            if not isinstance(record, Mapping):
                unmeasured += 1
                continue
            solar = record.get("solar_w")
            grid = record.get("grid_w")
            if _is_number(solar) and _is_number(grid):
                valid_solar += float(solar)
                valid_grid += float(grid)
                measured += 1
            else:
                unmeasured += 1
        total = valid_solar + valid_grid
        if measured == 0 or total <= 0:
            return {
                "status": "UNKNOWN",
                "self_sufficiency_share": None,
                "measured_intervals": measured,
                "unmeasured_intervals": unmeasured,
                "reason": "no usable measurement; UNKNOWN is never HEALTHY",
            }
        return {
            "status": "MEASURED",
            "self_sufficiency_share": round(valid_solar / total, 6),
            "measured_intervals": measured,
            "unmeasured_intervals": unmeasured,
            "solar_wh": round(valid_solar, 6),
            "grid_wh": round(valid_grid, 6),
        }


class RegionalLoopIndicator:
    """Share of locally consumed units that were locally produced.

    Config comes from a local JSON mapping: {"local_produced": x, "local_consumed": y}.
    Missing or negative values yield UNKNOWN; nothing is estimated.
    """

    def __init__(self, config: Mapping[str, object]) -> None:
        if not isinstance(config, Mapping):
            raise AutarkyMetricError("config must be a mapping")
        self._config = dict(config)

    def compute(self) -> dict:
        produced = self._config.get("local_produced")
        consumed = self._config.get("local_consumed")
        if not _is_number(produced) or not _is_number(consumed):
            return {"status": "UNKNOWN", "local_loop_share": None,
                    "reason": "local_produced/local_consumed missing or invalid"}
        produced_f, consumed_f = float(produced), float(consumed)
        if consumed_f <= 0:
            return {"status": "UNKNOWN", "local_loop_share": None,
                    "reason": "local_consumed must be positive"}
        return {
            "status": "MEASURED",
            "local_loop_share": round(min(produced_f / consumed_f, 1.0), 6),
            "local_produced": produced_f,
            "local_consumed": consumed_f,
        }


class BiodiversityLog:
    """Optional observation diary: counting only, no assessment.

    SHA-256 hash-chained JSONL, same fail-closed pattern as the emergency ledger.
    """

    def __init__(self, log_path: str | os.PathLike,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.log_path = Path(log_path).expanduser().resolve()
        self._clock = clock
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_entries(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        entries: list[dict] = []
        with closing(open(self.log_path, "r", encoding="utf-8")) as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AutarkyMetricError(f"corrupt biodiversity log line: {exc}") from exc
                if not isinstance(entry, dict):
                    raise AutarkyMetricError("biodiversity log entry must be a JSON object")
                entries.append(entry)
        return entries

    def add_observation(self, species: str, count: int, note: str = "") -> dict:
        if not isinstance(species, str) or not species.strip():
            raise AutarkyMetricError("species must be a non-empty string")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise AutarkyMetricError("count must be a non-negative integer")
        entries = self._read_entries()
        if entries and not self.verify_chain():
            raise AutarkyMetricError("existing biodiversity log chain is invalid; append refused")
        prev = entries[-1]["entry_hash"] if entries else "0" * 64
        record = {
            "seq": len(entries) + 1,
            "species": species.strip(),
            "count": count,
            "note": note if isinstance(note, str) else "",
            "observed_at_utc": self._clock().isoformat(timespec="seconds").replace("+00:00", "Z"),
            "prev_hash": prev,
        }
        record["entry_hash"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        with closing(open(self.log_path, "a", encoding="utf-8")) as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for index, entry in enumerate(self._read_entries(), start=1):
            if not isinstance(entry, dict):
                return False
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            entry_hash = entry.get("entry_hash")
            if not isinstance(entry_hash, str) or len(entry_hash) != 64:
                return False
            expected = {k: v for k, v in entry.items() if k != "entry_hash"}
            digest = hashlib.sha256(
                json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if digest != entry_hash:
                return False
            prev = entry_hash
        return True

    def totals(self) -> dict:
        entries = self._read_entries()
        totals: dict[str, int] = {}
        for entry in entries:
            species = str(entry.get("species", "UNKNOWN"))
            count = entry.get("count")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                totals[species] = totals.get(species, 0) + count
        return {"observations": len(entries), "totals": totals}

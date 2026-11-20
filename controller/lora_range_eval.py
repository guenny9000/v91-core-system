#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
LoRa range field-test log and on-demand evaluation (Issue #103 Umfeld).

Append-only JSONL log of received radio packet observations: each line
records the receiver-side outcome (ok True/False), the node id, the
frame sequence number as received, the radio metrics of that reception
(rssi_dbm, snr_db) and the measurement spot (note). evaluate() reads
the log back and aggregates per-spot and overall statistics.

Fail-closed rules:
- exact record schema, no unknown keys, no silently corrected values
- rssi_dbm/snr_db must be finite floats or None (UNKNOWN is recorded as
  missing, never guessed, never zero)
- per node, accepted (ok=True) records must have strictly ascending seq
  and strictly ascending rx_ts; duplicates/replays are refused, and
  rejected (ok=False) records never modify the accepted-seq floor:
  an unverified frame carries no trusted sequence
- every line is validated before append and fsynced
- unparseable or invalid lines during evaluation are counted and
  reported, never silently skipped

Honest limits (DOCUMENTED != MEASURED):
- LOG ANALYSIS != FIELD MEASUREMENT: this module never invents RSSI or
  SNR; values are caller-supplied observations of a physical receiver.
- The gap-based loss estimate assumes the sender emitted every sequence
  number exactly once, in order (operator's test setup). A gap between
  the two highest accepted seq values counts as missed packets;
  GAP ESTIMATE != GROUND TRUTH, and before the first accepted packet
  of a node no loss statement is made at all.
- Frame verification itself lives in mesh_frame_codec and
  federation_receiver (NO_DUPLICATE_SYSTEMS); this module only records
  their outcomes and never re-verifies crypto.
- No radio, no daemon, no network: SHIPPING != INSTALLATION.
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REQUIRED_KEYS = frozenset({
    "rx_ts", "node_id", "seq", "ok", "rssi_dbm", "snr_db", "note",
})
# written by append(), tolerated on read-back (restart-safe floors);
# never accepted as a caller input claim via validate_record on raw dicts.
_WRITTEN_ONLY_KEYS = frozenset({"missed_packets_since_last"})


class RangeLogError(ValueError):
    """Raised when a record violates the range-log contract (fail-closed)."""


@dataclass(frozen=True)
class SpotStats:
    note: str
    accepted: int = 0
    rejected: int = 0
    missed_packets: int = 0
    loss_percent: Optional[float] = None  # None when no basis (UNKNOWN)
    rssi_mean_dbm: Optional[float] = None
    rssi_min_dbm: Optional[float] = None
    rssi_max_dbm: Optional[float] = None
    rssi_missing: int = 0
    snr_mean_db: Optional[float] = None
    snr_min_db: Optional[float] = None
    snr_max_db: Optional[float] = None
    snr_missing: int = 0


@dataclass(frozen=True)
class RangeEvaluation:
    spots: tuple[SpotStats, ...] = ()
    total_accepted: int = 0
    total_rejected: int = 0
    total_missed: int = 0
    unparseable_lines: int = 0
    invalid_lines: int = 0


def _is_real_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validates one range-log record; returns a normalized copy."""
    if not isinstance(record, dict):
        raise RangeLogError("record_must_be_object")
    keys = set(record)
    read_keys = keys - _WRITTEN_ONLY_KEYS
    missed = record.get("missed_packets_since_last")
    if "missed_packets_since_last" in keys:
        if not isinstance(missed, int) or isinstance(missed, bool) or missed < 0:
            raise RangeLogError("invalid_missed_packets_since_last")
    if read_keys != _REQUIRED_KEYS:
        missing = sorted(_REQUIRED_KEYS - read_keys)
        unknown = sorted(read_keys - _REQUIRED_KEYS)
        raise RangeLogError(f"schema_violation:missing={missing}:unknown={unknown}")

    rx_ts = record["rx_ts"]
    if not isinstance(rx_ts, int) or isinstance(rx_ts, bool) or rx_ts <= 0:
        raise RangeLogError("invalid_rx_ts")

    node_id = record["node_id"]
    if not isinstance(node_id, str) or not node_id.strip():
        raise RangeLogError("invalid_node_id")

    seq = record["seq"]
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise RangeLogError("invalid_seq")

    ok = record["ok"]
    if not isinstance(ok, bool):
        raise RangeLogError("invalid_ok")

    note = record["note"]
    if not isinstance(note, str) or not note.strip():
        raise RangeLogError("invalid_note")

    normalized: dict[str, Any] = {
        "rx_ts": rx_ts,
        "node_id": node_id,
        "seq": seq,
        "ok": ok,
        "note": note,
    }
    for field in ("rssi_dbm", "snr_db"):
        value = record[field]
        if value is None:
            normalized[field] = None
        elif _is_real_number(value):
            normalized[field] = float(value)
        else:
            raise RangeLogError(f"invalid_{field}")
    return normalized


class RangeLog:
    """Append-only range-test log with per-node accepted-seq floors."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def _accepted_floors(self) -> dict[str, tuple[int, int]]:
        """Rebuilds per-node (last_seq, last_rx_ts) of accepted records, restart-safe."""
        floors: dict[str, tuple[int, int]] = {}
        if not self._path.exists():
            return floors
        with self._path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = validate_record(json.loads(line))
                except (json.JSONDecodeError, RangeLogError):
                    raise RangeLogError(
                        "log_corrupt_or_invalid: rebuild of accepted floors "
                        "requires a fully valid log (fail-closed, no repair)"
                    ) from None
                if not record["ok"]:
                    continue  # rejected records carry no trusted sequence
                key = record["node_id"]
                if key in floors:
                    if record["seq"] <= floors[key][0]:
                        raise RangeLogError("log_corrupt_or_invalid:seq_not_ascending")
                    if record["rx_ts"] <= floors[key][1]:
                        raise RangeLogError("log_corrupt_or_invalid:rx_ts_not_ascending")
                floors[key] = (record["seq"], record["rx_ts"])
        return floors

    def append(
        self,
        *,
        node_id: str,
        seq: int,
        ok: bool,
        rssi_dbm: float | None,
        snr_db: float | None,
        note: str,
        rx_ts: int,
    ) -> dict[str, Any]:
        """Validates and appends one observation; fsync before return."""
        record = validate_record({
            "rx_ts": rx_ts,
            "node_id": node_id,
            "seq": seq,
            "ok": ok,
            "rssi_dbm": rssi_dbm,
            "snr_db": snr_db,
            "note": note,
        })
        floors = self._accepted_floors()
        missed = 0
        if ok:
            if node_id in floors:
                last_seq, last_rx_ts = floors[node_id]
                if seq <= last_seq:
                    raise RangeLogError(
                        f"seq_not_ascending:{seq}_vs_last_accepted_{last_seq}: "
                        "duplicates/replays of accepted frames are refused; "
                        "rejected frames never raise the floor"
                    )
                if rx_ts <= last_rx_ts:
                    raise RangeLogError("rx_ts_not_ascending")
                missed = seq - last_seq - 1
        directory = self._path.parent
        directory.mkdir(parents=True, exist_ok=True)
        record_to_write = dict(record)
        record_to_write["missed_packets_since_last"] = missed
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record_to_write, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record_to_write

    def evaluate(self) -> RangeEvaluation:
        """Read-only per-spot and overall statistics; never repairs."""
        if not self._path.exists():
            raise RangeLogError(f"log_not_found:{self._path}")

        accepted_seq: dict[str, list[int]] = {}
        per_spot: dict[str, dict[str, Any]] = {}
        total_accepted = 0
        total_rejected = 0
        unparseable = 0
        invalid = 0

        with self._path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = validate_record(json.loads(line))
                except json.JSONDecodeError:
                    unparseable += 1
                    continue
                except RangeLogError:
                    invalid += 1
                    continue
                spot = record["note"]
                bucket = per_spot.setdefault(spot, {
                    "accepted": 0, "rejected": 0, "missed": 0,
                    "rssi": [], "snr": [], "rssi_missing": 0, "snr_missing": 0,
                })
                if record["ok"]:
                    if record["node_id"] in accepted_seq:
                        last = accepted_seq[record["node_id"]][-1]
                        gap = record["seq"] - last - 1
                        if gap > 0:
                            bucket["missed"] += gap
                    accepted_seq.setdefault(record["node_id"], []).append(record["seq"])
                    bucket["accepted"] += 1
                    total_accepted += 1
                else:
                    bucket["rejected"] += 1
                    total_rejected += 1
                if record["rssi_dbm"] is None:
                    bucket["rssi_missing"] += 1
                else:
                    bucket["rssi"].append(record["rssi_dbm"])
                if record["snr_db"] is None:
                    bucket["snr_missing"] += 1
                else:
                    bucket["snr"].append(record["snr_db"])

        spots = []
        for note in sorted(per_spot):
            b = per_spot[note]
            expected = b["accepted"] + b["missed"]
            loss = (b["missed"] / expected * 100.0) if expected > 0 else None
            spots.append(SpotStats(
                note=note,
                accepted=b["accepted"],
                rejected=b["rejected"],
                missed_packets=b["missed"],
                loss_percent=loss,
                rssi_mean_dbm=(sum(b["rssi"]) / len(b["rssi"])) if b["rssi"] else None,
                rssi_min_dbm=min(b["rssi"]) if b["rssi"] else None,
                rssi_max_dbm=max(b["rssi"]) if b["rssi"] else None,
                rssi_missing=b["rssi_missing"],
                snr_mean_db=(sum(b["snr"]) / len(b["snr"])) if b["snr"] else None,
                snr_min_db=min(b["snr"]) if b["snr"] else None,
                snr_max_db=max(b["snr"]) if b["snr"] else None,
                snr_missing=b["snr_missing"],
            ))
        return RangeEvaluation(
            spots=tuple(spots),
            total_accepted=total_accepted,
            total_rejected=total_rejected,
            total_missed=sum(s.missed_packets for s in spots),
            unparseable_lines=unparseable,
            invalid_lines=invalid,
        )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] not in {"append", "evaluate"}:
        print(
            "usage: lora_range_eval append <log> --node N --seq S --rx-ts T --note P "
            "[--rssi R --snr V --not-ok] | evaluate <log>",
            file=sys.stderr,
        )
        return 2
    command, log_path = args[0], Path(args[1])
    try:
        if command == "evaluate":
            evaluation = RangeLog(log_path).evaluate()
            print(json.dumps({
                "spots": [s.__dict__ for s in evaluation.spots],
                "total_accepted": evaluation.total_accepted,
                "total_rejected": evaluation.total_rejected,
                "total_missed": evaluation.total_missed,
                "unparseable_lines": evaluation.unparseable_lines,
                "invalid_lines": evaluation.invalid_lines,
            }, ensure_ascii=False, indent=2))
            return 0
        options: dict[str, str] = {}
        rest = args[2:]
        if len(rest) % 2 != 0:
            raise RangeLogError("append_needs_option_value_pairs")
        for i in range(0, len(rest), 2):
            options[rest[i].lstrip("-").replace("-", "_")] = rest[i + 1]
        for required in ("node", "seq", "rx_ts", "note"):
            if required not in options:
                raise RangeLogError(f"append_missing_option:{required}")
        rssi = None if "rssi" not in options else float(options["rssi"])
        snr = None if "snr" not in options else float(options["snr"])
        record = RangeLog(log_path).append(
            node_id=options["node"],
            seq=int(options["seq"]),
            ok="not_ok" not in options,
            rssi_dbm=rssi,
            snr_db=snr,
            note=options["note"],
            rx_ts=int(options["rx_ts"]),
        )
        print(json.dumps(record, ensure_ascii=False))
        return 0
    except (RangeLogError, ValueError) as error:
        print(f"FAILED_CLOSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

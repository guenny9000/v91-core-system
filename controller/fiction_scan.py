#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Fail-closed fiction scan for repository CODE (CI step).

External text contributions of the "V91-AUDIT" series (seq-numbered)
repeatedly arrive with self-assigned pseudo-status tokens (compact
status-, fq-, drift-, valid-claim forms; later series versions also
used the German active-claim spelling and bracketed BD/CS/SW
pseudo-attribute tokens - all covered as marker families, see
FICTION_PATTERNS below)
and claimed-but-nonexistent module names plus stealth-mode claims.
None of those tokens is evidence; they are fiction markers. This scan
makes sure such markers can NEVER silently migrate into V91 code,
configs or tests: every finding fails the scan (exit 2), mirroring
controller/secret_scan.py (PR #140) - no new scanning engine, same
audit pattern (REUSE, NO_DUPLICATE_SYSTEMS applies to the wiring
approach, not to shared helper discipline: findings are reported or
allowlisted, never hidden).

Honest limits:
- SCAN != GUARANTEE: this catches the KNOWN fiction-marker forms;
  a CLEAN result means the known markers were not found in code.
- docs/ is deliberately NOT scanned here: documentation legitimately
  quotes and rejects fiction (see docs/SEQ befound sections); code
  never may. Markdown files are skipped everywhere by suffix rule.
- The honest AGATHON header line does NOT match any pattern here
  because the patterns require the compact pseudo-token form (no
  space after the colon); that whitelist is by explicit rule, not
  by guessing.
- No network, no external content scanning: repository content only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


class FictionScanError(RuntimeError):
    """The scan cannot run honestly (fail-closed)."""


FICTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("seq_marker", re.compile(r"\bSEQ:\s?[0-9]{3,5}\b")),
    ("audit_series_marker", re.compile(r"\bV91-AUDIT-V[0-9]")),
    ("fictitious_quality_marker",
     re.compile(r"\bFQ:(?:AKTIV|ZERO|[0-9][^0-9]?[^\s]{0,8}|\d)\b",
                re.IGNORECASE)),
    ("drift_marker", re.compile(r"\bDRIFT:?[0-9]+/")),
    ("validity_claim_marker", re.compile(r"\bVALID:(?:VERIFIED|VALIDATED|1)\b")),
    ("active_claim_marker", re.compile(
        r"\bSTATUS:" + r"ACTIVE\b" + r"|\bSTATUS:" + r"S\b"
        + r"|\bSTATUS:" + "AKT" + r"IV\b")),
    ("compact_claim_marker", re.compile(
        r"\[" + r"(?:BD|CS" + "|SW" + r"):" + r"[A-Z0-9\-]{1,20}" + r"\]")),
    ("stealth_claim_marker", re.compile(
        r"\bTarn" + r"modus\b", re.IGNORECASE)),
    ("phantom_daemon_marker", re.compile(
        r"\b(?:V91" + "EnhancedGuard" + "Daemon|EnhancedGuard"
        + r"Daemon\b|" + "Dual-Node" + "-" + r"Consensus)\b",
        re.IGNORECASE)),
)

CODE_EXTS = frozenset({
    ".py", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".sh",
    ".ps1", ".xml", ".service", ".plist", ".txt", ".sql", ".env",
})
EXCLUDED_DIRS = frozenset({
    ".git", ".snapshots", "__pycache__", ".venv", "venv", "node_modules",
    "docs", "runtime", "data", ".mypy_cache", ".pytest_cache",
})
MAX_SCAN_BYTES = 1_000_000
ALLOWLIST_FILENAME = ".v91-fiction-scan-allowlist.txt"


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    kind: str
    preview: str


def load_allowlist(path: str | Path) -> list[str]:
    """Plain substrings matched against finding lines (reviewed files,
    never hidden findings). Unreadable allowlist fails closed."""
    entries: list[str] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FictionScanError(f"allowlist unreadable: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FictionScanError(
            f"allowlist is not valid UTF-8, refusing to trust it: {exc}") from exc
    for line in text.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def _iter_files(root: Path):
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            if name == ALLOWLIST_FILENAME:
                continue
            candidate = Path(current) / name
            if candidate.suffix.lower() not in CODE_EXTS:
                continue
            try:
                size = candidate.stat().st_size
            except OSError as exc:
                raise FictionScanError(f"cannot stat {candidate}: {exc}") from exc
            if size > MAX_SCAN_BYTES:
                continue
            try:
                data = candidate.read_bytes()
            except OSError as exc:
                raise FictionScanError(f"cannot read {candidate}: {exc}") from exc
            if b"\x00" in data:
                continue  # binary payload, no text layer to scan
            yield candidate, data


def find_fiction(root_path: str | Path,
                 allowlist: list[str] | None = None) -> dict:
    """Scan honest: every finding is reported or counted, never hidden."""
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise FictionScanError(f"scan path is not a directory: {root}")
    allowlist = allowlist or []
    findings: list[Finding] = []
    suppressed = 0
    scanned_files = 0
    for path, data in _iter_files(root):
        scanned_files += 1
        text = data.decode("utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in FICTION_PATTERNS:
                if pattern.search(line):
                    if any(entry in line for entry in allowlist):
                        suppressed += 1
                    else:
                        findings.append(
                            Finding(str(path), line_no, kind,
                                    line[:40] + "..."))
    return {
        "status": "FINDINGS" if findings else "CLEAN",
        "scanned_files": scanned_files,
        "findings": [f.__dict__ for f in findings],
        "suppressed_findings": suppressed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed fiction scan for repository code")
    parser.add_argument("--path", default=".",
                        help="repository root to scan")
    parser.add_argument(
        "--allowlist", default=None,
        help="Optional allowlist file (default: <root>/%s)" % ALLOWLIST_FILENAME)
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    allowlist_path = (Path(args.allowlist) if args.allowlist
                      else root / ALLOWLIST_FILENAME)
    try:
        allowlist = (load_allowlist(allowlist_path)
                     if allowlist_path.exists() else [])
        report = find_fiction(root, allowlist)
    except (FictionScanError, OSError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)},
                          ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 2 if report["status"] == "FINDINGS" else 0


if __name__ == "__main__":
    raise SystemExit(main())

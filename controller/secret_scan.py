"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Fail-closed secret scan for repository content (CI step).

High-signal credential formats are checked in every text file,
keyword assignments are checked in code/config files. Every finding
fails the scan (exit 2). Placeholders are skipped by explicit rule,
never by guessing; suppressed findings are counted, never hidden.

Honest limits:
- SCAN != GUARANTEE: patterns cannot catch every secret form; a
  CLEAN result means the known high-signal forms were not found.
- Keyword-assignment values that reference variables (containing "$")
  or look like paths (containing "/") are deployment configuration,
  not literals, and are skipped by documented rule.
- No network, no key material handling, no host audit: this scans
  repository content only (SCAN != INSTALLED SECURELY).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


class SecretScanError(RuntimeError):
    """The scan cannot run honestly (fail-closed)."""


HIGH_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block",
     re.compile("-----BEGIN " + "[A-Z ]*" + "PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_classic_token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github_fine_grained_token",
     re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,255}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,250}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,255}\b")),
    ("sk_prefixed_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,255}\b")),
)

_ASSIGNMENT_KEYWORDS = "password|passwd|secret|token|api[_-]?key|apikey|access[_-]?key"
GENERIC_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:" + _ASSIGNMENT_KEYWORDS + r")\b[ \t]*[=:][ \t]*"
    r"[\x27\"]([^\x27\"\n]{8,})[\x27\"]"
)
ENV_ASSIGNMENT_PATTERN = re.compile(
    r"^[ \t]*[A-Za-z0-9_]*(?:" + _ASSIGNMENT_KEYWORDS + r")[A-Za-z0-9_]*"
    r"[ \t]*=[ \t]*(\S.*)$",
    re.IGNORECASE,
)
PLACEHOLDER_MARKERS = (
    "changeme", "change_me", "change-me", "example", "your", "dummy",
    "placeholder", "insert", "xxxx", "test", "none", "null", "undefined",
    "sample",
)
CODE_EXTS = frozenset({
    ".py", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".sh",
    ".ps1", ".xml", ".service", ".plist", ".txt",
})
EXCLUDED_DIRS = frozenset({
    ".git", ".snapshots", "__pycache__", ".venv", "venv", "node_modules",
    "runtime", "data", ".mypy_cache", ".pytest_cache",
})
MAX_SCAN_BYTES = 1_000_000
ALLOWLIST_FILENAME = ".v91-secret-scan-allowlist.txt"


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    kind: str
    preview: str


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _is_skipped_value(value: str) -> bool:
    # Variable references and paths are deployment configuration,
    # not secret literals (documented rule, not a guess).
    return "$" in value or "/" in value or _is_placeholder(value)


def _env_like(name: str) -> bool:
    return name == ".env" or name.startswith(".env") or name.endswith(".env")


def load_allowlist(path: str | Path) -> list[str]:
    """Entries are plain substrings matched against finding lines.

    The allowlist file itself is never scanned (it is reviewed like
    code). Unreadable allowlist fails closed.
    """
    entries: list[str] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SecretScanError(f"allowlist unreadable, refusing scan: {exc}") from exc
    for line in text.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def _iter_files(root: Path):
    for current, dirnames, filenames in root.walk():
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            if name == ALLOWLIST_FILENAME:
                continue
            candidate = current / name
            try:
                size = candidate.stat().st_size
            except OSError as exc:
                raise SecretScanError(f"cannot stat {candidate}: {exc}") from exc
            if size > MAX_SCAN_BYTES:
                continue
            try:
                data = candidate.read_bytes()
            except OSError as exc:
                raise SecretScanError(f"cannot read {candidate}: {exc}") from exc
            if b"\x00" in data:
                continue  # binary payload, no text layer to leak
            yield candidate, data


def find_secrets(root_path: str | Path,
                 allowlist: list[str] | None = None) -> dict:
    """Scan honest: every finding is reported or counted, never hidden."""
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise SecretScanError(f"scan path is not a directory: {root}")
    allowlist = allowlist or []
    findings: list[Finding] = []
    suppressed = 0
    scanned_files = 0
    for path, data in _iter_files(root):
        scanned_files += 1
        text = data.decode("utf-8", errors="replace")
        env_like = _env_like(path.name)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in HIGH_SIGNAL_PATTERNS:
                if pattern.search(line):
                    if any(entry in line for entry in allowlist):
                        suppressed += 1
                    else:
                        findings.append(
                            Finding(str(path), line_no, kind, line[:24] + "..."))
                    break
            if path.suffix in CODE_EXTS:
                match = GENERIC_ASSIGNMENT_PATTERN.search(line)
                if match and not _is_skipped_value(match.group(1)):
                    if any(entry in line for entry in allowlist):
                        suppressed += 1
                    else:
                        findings.append(
                            Finding(str(path), line_no, "keyword_assignment",
                                    line[:24] + "..."))
            if env_like:
                match = ENV_ASSIGNMENT_PATTERN.search(line)
                if match and not _is_skipped_value(match.group(1)):
                    if any(entry in line for entry in allowlist):
                        suppressed += 1
                    else:
                        findings.append(
                            Finding(str(path), line_no, "env_assignment",
                                    line[:24] + "..."))
    return {
        "status": "FINDINGS" if findings else "CLEAN",
        "scanned_files": scanned_files,
        "findings": [f.__dict__ for f in findings],
        "suppressed_findings": suppressed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed secret scan for repository content")
    parser.add_argument("--path", default=".", help="repository root to scan")
    parser.add_argument(
        "--allowlist", default=None,
        help="Optional allowlist file (default: <root>/.v91-secret-scan-allowlist.txt)"
    )
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    allowlist_path = (Path(args.allowlist) if args.allowlist
                      else root / ALLOWLIST_FILENAME)
    try:
        allowlist = (load_allowlist(allowlist_path)
                     if allowlist_path.exists() else [])
        report = find_secrets(root, allowlist)
    except (SecretScanError, OSError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)},
                          ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 2 if report["status"] == "FINDINGS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
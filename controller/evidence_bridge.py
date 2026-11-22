"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
-----
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
-----
Evidence-Bridge (VIBE-LXXXVI, CLAIM 7085192096):
DUENNER ORCHESTRIERUNGS-ADAPTER, KEINE ZWEIT-AUSWERTUNG.
- Verbindet controller/repo_report_agent.py (VIBE-LXXXV, PR #393) mit dem
  Teil-C-Check-Vertrag von controller/daily_report.py (#277).
- FUERT den echten Repo-Report KEINMAL SELBST AUS: das lokale Pruefen bleibt
  allein im repo_report_agent (NO_DUPLICATE_SYSTEMS, kein Zweit-Lint, keine
  Zweit-Auswertung von violations/UNKNOWN-Keys).
- Liest den HEAD-SHA NUR aus lokalen .git-Dateien (read-only, kein subprocess,
  kein Netz). Kein Git-Checkout belegbar -> kein check, status UNKNOWN
  (UNKNOWN != PASS, es wird KEIN head_sha erfunden).
- verdrahtet != betreibt: SCRIPTED != INSTALLIERT, BRIDGE != AGENT.
Richtlinie: docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md, docs/V91-TAGESBERICHT-STANDARD.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from controller import repo_report_agent as _repo_report_agent
except ImportError:
    _repo_report_agent = None

TASK_ID = "VIBE-LXXXVI"
CHECK_NAME = "repo_report_agent (VIBE-LXXXV) via evidence_bridge"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 3


def resolve_head_sha(repo_root):
    """Liest den HEAD-Commit-SHA aus .git (read-only, stdlib, kein subprocess).

    Kein belegbarer Checkout -> None. KEIN Rateversuch, KEIN fake-SHA."""
    git_dir = repo_root / ".git"
    if git_dir.is_file():
        # worktree/Split-Index: "gitdir: <pfad>" in einer Datei
        first = git_dir.read_text(encoding="utf-8", errors="strict").strip()
        if not first.startswith("gitdir:"):
            return None
        git_dir = repo_root / first.split("gitdir:", 1)[1].strip()
    if not git_dir.is_dir():
        return None

    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    head = head_file.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split("ref:", 1)[1].strip()
        ref_file = git_dir / ref
        if ref_file.is_file():
            sha = ref_file.read_text(encoding="utf-8").strip()
            if sha:
                return sha
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0]
        return None
    return head or None


def _default_runner():
    if _repo_report_agent is None or not hasattr(_repo_report_agent, "build_report"):
        raise RuntimeError("repo_report_agent nicht importierbar - FAIL-CLOSED, die Bridge prueft nichts selbst")
    return _repo_report_agent.build_report


def build_snapshot(repo_root_str, runner=None, head_resolver=None):
    """Oeffentlicher Einstieg. Liefert (snapshot_dict, exit_code), FAIL-CLOSED.

    runner/head_resolver sind Injektionspunkte fuer deterministische Tests;
    produktiv wird der ECHTE repo_report_agent bzw. .git verwendet."""
    repo_root = Path(repo_root_str)
    if not repo_root.is_dir():
        snapshot = {
            "task_id": TASK_ID,
            "status": "FAIL",
            "check": None,
            "unknown_keys": [],
            "head_sha": None,
            "reason": "INPUT_ERROR: repo_root existiert nicht",
        }
        return snapshot, EXIT_INPUT_ERROR

    run = runner if runner is not None else _default_runner()
    report, exit_code = run(str(repo_root))

    status = "PASS" if exit_code == 0 and not report.get("violations") else "FAIL"
    check = {
        "name": CHECK_NAME,
        "head_sha": "",
        "conclusion": "success" if status == "PASS" else "failure",
        "violations": list(report.get("violations", [])),
        "unknown_keys": list(report.get("unknown_keys", [])),
    }
    if head_resolver is not None:
        head_sha = head_resolver(str(repo_root))
    else:
        head_sha = resolve_head_sha(repo_root)

    if not head_sha:
        # KEIN erfundener head_sha: Ohne belegbaren Checkout gibt es KEINEN
        # Teil-C-check (daily_report stuende sonst auf unbewiesener Basis).
        snapshot = {
            "task_id": TASK_ID,
            "status": "UNKNOWN",
            "check": None,
            "unknown_keys": list(report.get("unknown_keys", []))
            + ["repo_head_sha"],
            "head_sha": None,
            "reason": "HEAD_SHA_UNRESOLVED: kein Git-Checkout belegbar, kein check geliefert",
        }
        return snapshot, EXIT_FAIL

    check["head_sha"] = head_sha
    snapshot = {
        "task_id": TASK_ID,
        "status": status,
        "check": check,
        "unknown_keys": list(report.get("unknown_keys", [])),
        "head_sha": head_sha,
        "reason": "check bereit fuer daily_report Teil C (data['checks'].append(snapshot['check']))",
    }
    return snapshot, (EXIT_OK if status == "PASS" else EXIT_FAIL)


def export_snapshot_json(snapshot):
    """Deterministische, maschinenlesbare Serialisierung des Snapshots."""
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence-Bridge repo_report_agent -> daily_report Teil C (read-only)")
    parser.add_argument("--repo-root", default=".", help="Wurzelverzeichnis des Repository-Checkouts")
    parser.add_argument("--json-out", default=None, help="OPTIONAL: Snapshot-JSON in lokale Datei (nur auf expliziten Aufruf)")
    args = parser.parse_args(argv)
    snapshot, _exit = build_snapshot(args.repo_root)
    printed = export_snapshot_json(snapshot)
    print(printed)
    if args.json_out:
        Path(args.json_out).write_text(printed + "\n", encoding="utf-8")
    return _exit


if __name__ == "__main__":
    sys.exit(main())

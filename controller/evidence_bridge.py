"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Evidence-Bridge (VIBE-LXXXVI, CLAIM 7085192096; Review-Fixes 7085274526):
DUENNER ORCHESTRIERUNGS-ADAPTER, KEINE ZWEIT-AUSWERTUNG.
- Verbindet controller/repo_report_agent.py (VIBE-LXXXV, PR #393) mit dem
  Teil-C-Check-Vertrag von controller/daily_report.py (#277).
- FUERT den echten Repo-Report KEINMAL SELBST AUS: das lokale Pruefen bleibt
  allein im repo_report_agent (NO_DUPLICATE_SYSTEMS, kein Zweit-Lint).
- UNKNOWN-Semantik bleibt sichtbar: unknown_keys wandern als unknown_notes
  in den Teil-C-Check; daily_report zeigt dann AMBER statt GREEN.
- Liest den HEAD-SHA NUR aus lokalen .git-Dateien (read-only, kein subprocess,
  kein Netz). Nur 40/64 Hex-Zeichen akzeptiert, Ref-Namen gegen Pfad-Traversal
  geprueft, Worktree/gitdir- und commondir-Faelle ohne belegbaren HEAD bleiben
  UNKNOWN (UNKNOWN != PASS, es wird KEIN head_sha erfunden).
- verdrahtet != betreibt: SCRIPTED != INSTALLED, BRIDGE != AGENT,
  INTEGRATION_PENDING: kein automatisch laufender Tagesberichtsbetrieb,
  kein Daemon, kein Timer; Aufruf bleibt ein geplanter Schritt.
Richtlinie: docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md, docs/V91-TAGESBERICHT-STANDARD.md
"""
from __future__ import annotations

import argparse
import json
import re
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

# Fix 3 (Review 7085274526): Nur echte Git-SHAS, 40 Hex (SHA-1) oder 64 Hex (SHA-256).
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")
# Fix 3: Ref-Namen ohne Pfad-Traversal (".." oder absolute/relative Escape-Pfade).
_REF_RE = re.compile(r"^refs/[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _valid_sha(value):
    return isinstance(value, str) and _SHA_RE.match(value.strip()) is not None


def _valid_ref(value):
    return isinstance(value, str) and _REF_RE.match(value) is not None and ".." not in value


def resolve_head_sha(repo_root):
    """Liest den HEAD-Commit-SHA aus .git (read-only, stdlib, kein subprocess).

    Kein belegbarer Checkout -> None. KEIN Rateversuch, KEIN fake-SHA.
    Worktree/Split-Faelle (gitdir-Datei, commondir) ohne belegbaren HEAD
    bleiben ehrlich None (UNKNOWN), statt mit Teilpfaden zu raten."""
    git_dir = repo_root / ".git"
    if git_dir.is_file():
        first = git_dir.read_text(encoding="utf-8", errors="strict").strip()
        if not first.startswith("gitdir:"):
            return None
        git_dir = repo_root / first.split("gitdir:", 1)[1].strip()
        if not git_dir.is_dir():
            return None
        # commondir (Worktree teilt refs mit Haupt-Repo): explizit NICHT geraten;
        # ohne eigenen belegbaren HEAD bleibt der Fall UNKNOWN.
        if (git_dir / "commondir").is_file():
            return None
    if not git_dir.is_dir():
        return None

    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    head = head_file.read_text(encoding="utf-8", errors="strict").strip()
    if head.startswith("ref:"):
        ref = head.split("ref:", 1)[1].strip()
        if not _valid_ref(ref):
            return None
        ref_file = git_dir / ref
        if ref_file.is_file():
            sha = ref_file.read_text(encoding="utf-8", errors="strict").strip()
            if _valid_sha(sha):
                return sha
            return None
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.endswith(" " + ref):
                    sha = line.split(" ", 1)[0]
                    if _valid_sha(sha):
                        return sha
        return None
    return head if _valid_sha(head) else None


def _default_runner():
    if _repo_report_agent is None or not hasattr(_repo_report_agent, "build_report"):
        raise RuntimeError("repo_report_agent nicht importierbar - FAIL-CLOSED, die Bridge prueft nichts selbst")
    return _repo_report_agent.build_report


def _fail_snapshot(reason, task_reason_only=False):
    return {
        "task_id": TASK_ID,
        "status": "FAIL",
        "check": None,
        "unknown_keys": [],
        "head_sha": None,
        "reason": reason,
    }


def build_snapshot(repo_root_str, runner=None, head_resolver=None):
    """Oeffentlicher Einstieg. Liefert (snapshot_dict, exit_code), FAIL-CLOSED.

    runner/head_resolver sind Injektionspunkte fuer deterministische Tests;
    produktiv wird der ECHTE repo_report_agent bzw. .git verwendet.
    Fix 2: Runner-Ausnahmen und ungueltige Rueckgaben ergeben einen
    STRUKTURIERTEN FAIL-Snapshot statt eines ungefaengen Crashes."""
    repo_root = Path(repo_root_str)
    if not repo_root.is_dir():
        return _fail_snapshot("INPUT_ERROR: repo_root existiert nicht"), EXIT_INPUT_ERROR

    run = runner if runner is not None else _default_runner()
    try:
        result = run(str(repo_root))
    except Exception as exc:  # noqa: BLE001 - FAIL-CLOSED: jede Exception wird strukturiert
        return _fail_snapshot("RUNNER_EXCEPTION: %s" % exc), EXIT_FAIL

    if not isinstance(result, tuple) or len(result) != 2:
        return _fail_snapshot("RUNNER_INVALID_RETURN: erwarte (report, exit_code)"), EXIT_FAIL
    report, exit_code = result
    if not isinstance(report, dict):
        return _fail_snapshot("RUNNER_INVALID_RETURN: report ist kein dict"), EXIT_FAIL
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return _fail_snapshot("RUNNER_INVALID_RETURN: exit_code ist kein int"), EXIT_FAIL
    violations = report.get("violations", [])
    unknown_keys = report.get("unknown_keys", [])
    if not isinstance(violations, list):
        return _fail_snapshot("RUNNER_INVALID_RETURN: violations ist keine Liste"), EXIT_FAIL
    if not isinstance(unknown_keys, list):
        return _fail_snapshot("RUNNER_INVALID_RETURN: unknown_keys ist keine Liste"), EXIT_FAIL

    status = "PASS" if exit_code == 0 and not violations else "FAIL"
    check = {
        "name": CHECK_NAME,
        "head_sha": "",
        "conclusion": "success" if status == "PASS" else "failure",
        "violations": list(violations),
        # Fix 1: UNKNOWN-Felder bleiben im Teil C sichtbar (AMBER, nie stilles GREEN).
        "unknown_notes": list(unknown_keys),
    }
    if head_resolver is not None:
        head_sha = head_resolver(str(repo_root))
    else:
        head_sha = resolve_head_sha(repo_root)

    if not head_sha:
        # KEIN erfundener head_sha: Ohne belegbaren Checkout gibt es KEINEN
        # Teil-C-check (daily_report stuende sonst auf unbewiesener Basis).
        return ({
            "task_id": TASK_ID,
            "status": "UNKNOWN",
            "check": None,
            "unknown_keys": list(unknown_keys) + ["repo_head_sha"],
            "head_sha": None,
            "reason": "HEAD_SHA_UNRESOLVED: kein Git-Checkout belegbar, kein check geliefert",
        }, EXIT_FAIL)

    check["head_sha"] = head_sha
    return ({
        "task_id": TASK_ID,
        "status": status,
        "check": check,
        "unknown_keys": list(unknown_keys),
        "head_sha": head_sha,
        "reason": "check bereit fuer daily_report Teil C (data['checks'].append(snapshot['check']))",
    }, (EXIT_OK if status == "PASS" else EXIT_FAIL))


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

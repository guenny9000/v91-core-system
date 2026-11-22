"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
-----
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
-----
Repo-Report-Agent (VIBE-LXXXV, CLAIM 7084922874):
ORCHESTRATOR UEBER BESTANDSMODULE, KEIN ZWEIT-LINT, KEINE NEUE REGISTRY.
- Prueft den tatsaechlichen Repository-Zustand (Index, docs/).
- Vergleicht Behauptungen gegen Belege, wo Belege lokale Files sind.
- Ehrliches UNKNOWN fuer alles, was ohne Netz nicht belegbar ist
  (CI, PR, Merge-Zustaende, offene Issues).
- NUR LESE-ZUGRIFF auf den Repository-Baum; keine Schreib- oder
  Netzzugriffe im Repo (FAIL-CLOSED).
- LINT_OK != INHALT_GEPRUEFT, WARN != FAIL, SCRIPTED != AUTONOM.
Richtlinie: docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from controller.index_lint import check_file as _lint_check_file
    from controller.index_lint import build_report as _lint_build_report
except ImportError:
    _lint_check_file = None
    _lint_build_report = None

UNKNOWN_KEYS = (
    "ci_state_of_latest_prs",
    "merge_state_of_open_prs",
    "open_issue_count",
    "issue_220_claim_history",
    "live_github_network_data",
)

REQUIRED_DOCS = (
    "V91-GRUNDSATZ-KEIN-TOETEN.md",
    "V91-MAX-BEST-GESAMTSTRATEGIE-2026.md",
    "V91-AGENTEN-ARBEITSARCHITEKTUR.md",
    "V91-ARCHITEKTUR-INDEX.md",
)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 3


def _docs_inventory(repo_root):
    docs_dir = repo_root / "docs"
    if not docs_dir.is_dir():
        return {"status": "MISSING_DOCS_DIR", "present": [], "missing": list(REQUIRED_DOCS), "docs_md_total": 0}
    present = []
    missing = []
    for name in REQUIRED_DOCS:
        if (docs_dir / name).is_file():
            present.append(name)
        else:
            missing.append(name)
    return {
        "status": "OK" if not missing else "REQUIRED_DOC_MISSING",
        "present": present,
        "missing": missing,
        "docs_md_total": len(list(docs_dir.glob("*.md"))),
    }


def _compose_report(repo_root, index_path):
    """Baut den Repo-Report aus index_lint + docs_inventory + ehrlichen UNKNOWN."""
    if _lint_check_file is None or _lint_build_report is None:
        raise RuntimeError("index_lint nicht importierbar - FAIL-CLOSED, kein eigener Lint-Ersatz")

    lint_result, lint_code = _lint_check_file(str(index_path))
    if lint_code == 3:
        return (
            {"violations": [{"rule": "INDEX_NOT_READABLE", "detail": str(index_path)}],
             "unknown_keys": list(UNKNOWN_KEYS)},
            EXIT_INPUT_ERROR,
        )
    lint_report = _lint_build_report(lint_result, str(index_path))
    docs_report = _docs_inventory(repo_root)

    violations = []
    if lint_report.get("errors", 0) > 0:
        violations.append({"rule": "INDEX_LINT_ERRORS", "detail": "%d Fehler im Architektur-Index" % lint_report["errors"]})
    if docs_report["status"] != "OK":
        violations.append({"rule": "REQUIRED_DOC_MISSING", "detail": ",".join(docs_report["missing"])})

    report = {
        "index_lint": lint_report,
        "docs_inventory": docs_report,
        "unknown_keys": list(UNKNOWN_KEYS),
        "unknown_value": "UNKNOWN - ohne Netz-/Live-Zugriff hier NICHT belegbar (kein Behauptungsbetrieb)",
        "violations": violations,
        "limits": "SCRIPTED != AUTONOM, DOKUMENTIERT != RUNNING, LINT_OK != INHALT_GEPRUEFT, READ_ONLY",
    }
    return report, (EXIT_OK if not violations else EXIT_FAIL)


def build_report(repo_root_str):
    """Oeffentlicher Einstieg: Liefert (report_dict, exit_code)."""
    repo_root = Path(repo_root_str)
    if not repo_root.is_dir():
        return (
            {"violations": [{"rule": "REPO_ROOT_NOT_FOUND", "detail": repo_root_str}],
             "unknown_keys": list(UNKNOWN_KEYS)},
            EXIT_INPUT_ERROR,
        )
    index_path = repo_root / "docs" / "V91-ARCHITEKTUR-INDEX.md"
    return _compose_report(repo_root, index_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Repo-Report-Agent (Orchestrator, read-only)")
    parser.add_argument("--repo-root", default=".", help="Wurzelverzeichnis des Repository-Checkouts")
    parser.add_argument("--json-out", default=None, help="OPTIONAL: JSON-Report in lokale Datei (nur auf expliziten Aufruf)")
    args = parser.parse_args(argv)
    report, _exit = build_report(args.repo_root)
    printed = json.dumps(report, indent=2, sort_keys=True)
    print(printed)
    if args.json_out:
        Path(args.json_out).write_text(printed + "\n", encoding="utf-8")
    if report["violations"]:
        print("FAIL: %d Verletzung(en) gefunden" % len(report["violations"]))
        for v in report["violations"]:
            print("  %s: %s" % (v["rule"], v["detail"]))
        return EXIT_FAIL
    print("OK: Repo-Report erstellt, keine Verletzung, UNKNOWN ehrlich gekennzeichnet")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

"""Prune-Verriegelung Issue #591 (Abendlauf 2026-11-27).

Pinnt die gemessene Entscheidung des Dependency-Prune:
- requirements.txt deklariert NUR cryptography als Runtime-Abhaengigkeit
  (AST-Nachweis GENUTZT, 20+ Fundstellen).
- numpy und redis sind NICHT_GEFUNDEN_IN_PY (0 Fundstellen) und duerfen
  nicht still zurueckkehren (REGRESSION != RUECKKEHR).
- pytest ist Dev-Extra (requirements-dev.txt) und bleibt aus der
  Runtime-Datei draussen.
- INSTALLATION != NUTZUNG: der Windows-Prueflauf installiert numpy nicht
  mehr.

Fail-closed: Bei Abweichung schlagen die Tests ROT, bevor ein Commit
die gemessene Menge aendert. NICHT_GEFUNDEN != UNGENUTZT bleibt in
docs/V91-DEPENDENCY-AUDIT-2026-11-26.md dokumentiert.
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

from dependency_audit import parse_requirements  # noqa: E402

ALLOWED_RUNTIME = {"cryptography"}


def _runtime_packages() -> set:
    packages = parse_requirements(str(REPO_ROOT / "requirements.txt"))
    return {r.name for r in packages}


def _raw_requirements() -> str:
    return (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_runtime_deps_exactly_cryptography():
    assert _runtime_packages() == ALLOWED_RUNTIME


def test_pruned_packages_stay_out():
    text = _raw_requirements().lower()
    for banned in ("numpy", "redis", "pytest"):
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            assert not stripped.lower().startswith(banned), (
                f"{banned} kehrte ohne Messnachweis zurueck: {stripped}"
            )


def test_cryptography_usage_evidenced_by_ast_audit():
    from dependency_audit import collect_py_imports

    imports = collect_py_imports(str(REPO_ROOT))
    assert "cryptography" in imports, (
        "cryptography muss GENUTZT sein, sonst gehoert es nicht in requirements"
    )
    assert len(imports["cryptography"]) >= 1


def test_dev_requirements_chain_intact():
    raw = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in raw, (
        "requirements-dev.txt muss die Runtime-Datei einbinden"
    )
    dev_packages = {r.name for r in parse_requirements(
        str(REPO_ROOT / "requirements-dev.txt"))}
    assert "pytest" in dev_packages, "pytest bleibt Dev-Extra"


def test_windows_verify_workflow_installs_no_numpy():
    workflow = (REPO_ROOT / ".github" / "workflows" /
                "windows-local-verify.yml").read_text(encoding="utf-8")
    for line in workflow.splitlines():
        if "pip install" in line:
            assert "numpy" not in line, (
                "INSTALLATION != NUTZUNG: numpy darf im Windows-Prueflauf "
                "nicht mehr installiert werden"
            )


def test_prune_documented_in_dependency_audit_doc():
    doc = (REPO_ROOT / "docs" /
           "V91-DEPENDENCY-AUDIT-2026-11-26.md").read_text(encoding="utf-8")
    assert "Prune-Vollzug 2026-11-27" in doc
    assert "NICHT_GEFUNDEN != UNGENUTZT" in doc

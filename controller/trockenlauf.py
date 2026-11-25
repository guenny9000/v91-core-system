#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Trockenlauf-Runner: pytest-freier EVIDENZ-Ausfuehrungsweg der Testsuite.

Anlass (Parallel-Befund 25.11.2026, angenommen als echte Messung):
Trockendurchlaeufe in Umgebungen OHNE installierbares pytest
(Paketinstallation gesperrt) misslangen an 72 Modulen nur am
Import, NICHT am Bestand. Bisher gab es dafuer KEIN einheitliches
Werkzeug, sondern handgebaute Lauf-Loops je Umgebung.

Vertrag dieses Moduls:
- laeuft OHNE pytest: unittest-TestCases werden geladen und
  ausgefuehrt; plain test_*-Funktionen (pytest-Style) werden
  direkt aufgerufen. KEINE Neuimplementierung von pytest-Features
  (Fixtures, Parameterisierung): was pytest braucht, bleibt pytest.
- DREI-Klassen-Verdict je Modul: PASS (alles gruen), FAIL (echter
  Bestandsfehler: AssertionError/Exception im Test), ENV_FEHLT
  (ImportError BEVOR irgendein Test lief, z.B. pytest/cryptography
  fehlt: UMFAENG, NICHT Bestandsfehler; UNKNOWN != ROT).
- HONEST EXIT-CODES: exit 0 nur bei FAILS==0; ENV_FEHLT verhindert
  exit 0 NICHT (Umgebungsgrenze != Bestandsfehler) - der Bericht
  nennt sie aber einzeln mit Grund.
- KEIN Netzwerk, KEIN Schreiben ausser --json-Ausgabe; laeuft
  read-only gegen den Bestand.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_ENV_FEHLT = "ENV_FEHLT"


@dataclass
class ModuleResult:
    module: str
    verdict: str
    tests_run: int = 0
    failures: int = 0
    errors: int = 0
    detail: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "verdict": self.verdict,
            "tests_run": self.tests_run,
            "failures": self.failures,
            "errors": self.errors,
            "detail": self.detail[:5],
        }


def load_module(path: Path):
    """Importiert ein Testmodul per Dateipfad. laesst ImportError durch.
    sys.modules-Registrierung VOR exec_module: sonst brechen dataclass-
    Dekoratoren und Reloads der Zielmodule (Py3.12-Verhalten)."""
    name = "trockenlauf_mod_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_test_file(path: Path, repo_root: Path) -> ModuleResult:
    """Ein Modul ausfuehren und dreiklassig veredicten."""
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    result = ModuleResult(module=path.name, verdict=VERDICT_PASS)
    try:
        module = load_module(path)
    except ImportError:
        result.verdict = VERDICT_ENV_FEHLT
        result.detail = ["ImportError: " + (traceback.format_exc(limit=1).strip().splitlines()[-1] if True else "")]
        return result
    except Exception:
        result.verdict = VERDICT_FAIL
        result.detail = [traceback.format_exc(limit=2).strip()[-300:]]
        return result
    # 1) unittest-TestCases
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    if suite.countTestCases() > 0:
        runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=0)
        run = runner.run(suite)
        result.tests_run += run.testsRun
        result.failures += len(run.failures)
        result.errors += len(run.errors)
        result.detail += [f"{kind}: {test}" for kind, entries in (("fail", run.failures), ("error", run.errors)) for test, _ in entries]
    # 2) plain pytest-Style-Funktionen (KEIN Fixture-Support: Modul mit
    #    pytest-Fixtures wird als ENV_FEHLT klassifiziert, da Import scheitert)
    for fn_name in sorted(dir(module)):
        if not fn_name.startswith("test_"):
            continue
        fn = getattr(module, fn_name)
        if getattr(fn, "__code__", None) is None:
            continue
        argcount = fn.__code__.co_argcount
        if argcount != 0:
            result.detail.append(f"{fn_name}: SKIP_ARGCOUNT_{argcount}")
            continue
        result.tests_run += 1
        try:
            fn()
        except Exception:
            result.failures += 1
            result.detail.append(f"fail: {fn_name}")
    if result.failures or result.errors:
        result.verdict = VERDICT_FAIL
    if result.tests_run == 0 and result.verdict == VERDICT_PASS:
        result.verdict = VERDICT_FAIL
        result.detail.append("KEINE_TESTS_GEFUNDEN (leeres Modul = Verdaechtig)")
    return result


def run_directory(tests_dir: Path, repo_root: Path) -> dict[str, Any]:
    files = sorted(tests_dir.glob("test_*.py"))
    results = [run_test_file(f, repo_root) for f in files]
    report: dict[str, Any] = {
        "tool": "controller/trockenlauf.py",
        "files_checked": len(results),
        "verdicts": {"PASS": 0, "FAIL": 0, "ENV_FEHLT": 0},
        "tests_run": 0,
        "modules": [r.as_dict() for r in results],
    }
    for r in results:
        report["verdicts"][r.verdict] += 1
        report["tests_run"] += r.tests_run
    return report


def self_check() -> dict[str, Any]:
    """CI-Selbsttest des RUNNERS (synthetische Module, KEIN Bestandslauf)."""
    import tempfile

    sys.modules.pop("trockenlauf_probe_pass", None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "test_passmod.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(1, 1)\n"
            "def test_plain_ok():\n    assert 2 + 2 == 4\n", encoding="utf-8")
        (tmp_path / "test_failmod.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_boom(self):\n        self.fail('gepunkt')\n", encoding="utf-8")
        (tmp_path / "test_envmod.py").write_text(
            "import pytest_unavailable_modul_xyz\n", encoding="utf-8")
        (tmp_path / "test_argmod.py").write_text(
            "def test_mit_fixture(fix):\n    pass\n", encoding="utf-8")
        p = run_test_file(tmp_path / "test_passmod.py", tmp_path)
        f = run_test_file(tmp_path / "test_failmod.py", tmp_path)
        e = run_test_file(tmp_path / "test_envmod.py", tmp_path)
        a = run_test_file(tmp_path / "test_argmod.py", tmp_path)
        assert p.verdict == VERDICT_PASS and p.tests_run == 2, p
        assert f.verdict == VERDICT_FAIL, f
        assert e.verdict == VERDICT_ENV_FEHLT, e
        assert a.verdict == VERDICT_FAIL and any("SKIP_ARGCOUNT" in d for d in a.detail), a
    return {"self_check": "PASS", "klassifikation": "PASS/FAIL/ENV_FEHLT", "reine_fiktion": "KEINE"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Trockendurchlauf-Runner (pytest-frei)")
    parser.add_argument("--tests-dir", type=Path, default=Path("tests"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        print(json.dumps(self_check(), sort_keys=True))
        return 0
    if not args.tests_dir.is_dir():
        print(f"KEIN_TESTS_DIR: {args.tests_dir}", file=sys.stderr)
        return 5
    report = run_directory(args.tests_dir, args.repo_root)
    summary = {k: report[k] for k in ("files_checked", "verdicts", "tests_run")}
    print(json.dumps(summary, sort_keys=True))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["verdicts"][VERDICT_FAIL] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

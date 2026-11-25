"""Tests fuer controller/evidenz_collector.py (self-contained, nur tempfile)."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from controller import evidenz_collector as ec
except ImportError:  # Skript-Modus
    sys.path.insert(0, str(REPO_ROOT / "controller"))
    import evidenz_collector as ec  # type: ignore

COMMIT = "a" * 40
NOW = "2026-11-26T10:00:00+00:00"


def _write_artifact(base: pathlib.Path, name: str, content: bytes) -> str:
    path = base / name
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _plan(base: pathlib.Path, artifact: str, sha256: str) -> dict:
    return {
        "base_dir": str(base),
        "items": [
            {
                "label": "demo",
                "artifact": artifact,
                "sha256": sha256,
                "commit_sha": COMMIT,
                "gemessen_at": "2026-11-26T09:00:00+00:00",
                "methode": "selbstgebauter Fixture-Abgleich",
                "erwartung": "Artefakt liegt unveraendert vor",
                "ergebnis": "Artefakt geprueft",
            }
        ],
    }


class EvidenzCollectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, plan, now=NOW):
        return ec.collect_evidence(plan, ec.datetime.datetime.fromisoformat(now))

    def test_verifiziert_wenn_sha_passt(self):
        sha = _write_artifact(self.base, "report.csv", b"messreihe,1,2,3")
        out = self._run(_plan(self.base, "report.csv", sha))
        self.assertEqual(out["status"], ec.GESAMT_VERIFIZIERT)
        self.assertEqual(out["verified_items"], 1)
        self.assertEqual(out["items"][0]["status"], ec.STATUS_VERIFIZIERT)
        self.assertIn("FILE_EXISTS != VERIFIED_IMPROVEMENT", " ".join(out["honest_limits"]))

    def test_sha_mismatch_bleibt_nicht_geprueft(self):
        _write_artifact(self.base, "report.csv", b"messreihe")
        out = self._run(_plan(self.base, "report.csv", "0" * 64))
        self.assertEqual(out["status"], ec.GESAMT_UNVOLLSTAENDIG)
        self.assertEqual(out["items"][0]["status"], ec.STATUS_NICHT_GEPRUEFT)
        self.assertEqual(out["items"][0]["grund"], "SHA256_MISMATCH")

    def test_artefakt_fehlt_fail_closed(self):
        out = self._run(_plan(self.base, "fehlt.csv", "1" * 64))
        self.assertEqual(out["items"][0]["grund"], "ARTIFACT_MISSING")
        self.assertEqual(out["status"], ec.GESAMT_UNVOLLSTAENDIG)

    def test_pfadescape_wird_abgelehnt(self):
        sha = _write_artifact(self.base, "report.csv", b"x")
        out = self._run(_plan(self.base, "../report.csv", sha))
        self.assertEqual(out["items"][0]["status"], ec.STATUS_NICHT_GEPRUEFT)
        self.assertIn("EINGABE_FEHLER", out["items"][0]["grund"])

    def test_absoluter_pfad_wird_abgelehnt(self):
        out = self._run(_plan(self.base, str(self.base / "report.csv"), "1" * 64))
        self.assertIn("EINGABE_FEHLER", out["items"][0]["grund"])

    def test_handgesetztes_statusfeld_wird_ignoriert(self):
        sha = _write_artifact(self.base, "report.csv", b"messreihe")
        plan = _plan(self.base, "report.csv", sha)
        plan["items"][0]["status"] = "PASS"  # CLAIM duerfen nicht zaehlen
        out = self._run(plan)
        self.assertEqual(out["items"][0]["status"], ec.STATUS_VERIFIZIERT)  # nur weil SHA passt
        plan["items"][0]["sha256"] = "0" * 64  # jetzt ohne Beleg
        out = self._run(plan)
        self.assertEqual(out["items"][0]["status"], ec.STATUS_NICHT_GEPRUEFT)

    def test_naive_timestamps_abgelehnt(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        plan = _plan(self.base, "report.csv", sha)
        plan["items"][0]["gemessen_at"] = "2026-11-26T09:00:00"  # ohne timezone
        with self.assertRaises(ec.EvidenzCollectorError):
            self._run(plan)

    def test_zukuenftiger_messzeitpunkt_abgelehnt(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        plan = _plan(self.base, "report.csv", sha)
        plan["items"][0]["gemessen_at"] = "2026-11-27T09:00:00+00:00"
        with self.assertRaises(ec.EvidenzCollectorError):
            self._run(plan)

    def test_sha256_und_commit_formate_fail_closed(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        base_plan = _plan(self.base, "report.csv", sha)
        for field, bad in (("sha256", "kurz"), ("commit_sha", "abc")):
            plan = json.loads(json.dumps(base_plan))
            plan["items"][0][field] = bad
            with self.assertRaises(ec.EvidenzCollectorError):
                self._run(plan)

    def test_doppelte_labels_und_leere_items_abgelehnt(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        plan = _plan(self.base, "report.csv", sha)
        plan["items"].append(dict(plan["items"][0]))
        with self.assertRaises(ec.EvidenzCollectorError):
            self._run(plan)
        with self.assertRaises(ec.EvidenzCollectorError):
            self._run({"base_dir": str(self.base), "items": []})
        with self.assertRaises(ec.EvidenzCollectorError):
            self._run(["kein", "dict"])

    def test_plan_als_dateipfad(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        plan_path = self.base / "plan.json"
        plan_path.write_text(json.dumps(_plan(self.base, "report.csv", sha)), encoding="utf-8")
        out = ec.collect_evidence(str(plan_path), ec.datetime.datetime.fromisoformat(NOW))
        self.assertEqual(out["status"], ec.GESAMT_VERIFIZIERT)
        with open(plan_path, "w", encoding="utf-8") as fh:
            fh.write("{kein json")
        with self.assertRaises(ec.EvidenzCollectorError):
            ec.collect_evidence(str(plan_path), ec.datetime.datetime.fromisoformat(NOW))

    def test_ergebnis_nur_als_string(self):
        sha = _write_artifact(self.base, "report.csv", b"m")
        plan = _plan(self.base, "report.csv", sha)
        plan["items"][0]["ergebnis"] = 42
        out = self._run(plan)
        self.assertIsNone(out["items"][0]["ergebnis"])

    def test_cli_exitcodes(self):
        sha = _write_artifact(self.base, "report.csv", b"messreihe")
        plan_path = self.base / "plan.json"
        plan_path.write_text(json.dumps(_plan(self.base, "report.csv", sha)), encoding="utf-8")
        code = ec.main(["--plan", str(plan_path), "--now", NOW])
        self.assertEqual(code, 0)
        out_path = self.base / "out.json"
        code = ec.main(["--plan", str(plan_path), "--now", NOW, "--out", str(out_path)])
        self.assertEqual(code, 0)
        self.assertTrue(out_path.is_file())
        plan_path.write_text(json.dumps(_plan(self.base, "report.csv", "0" * 64)), encoding="utf-8")
        self.assertEqual(ec.main(["--plan", str(plan_path), "--now", NOW]), 1)
        self.assertEqual(ec.main([]), 2)
        bad_now = self.base / "now.json"
        bad_now.write_text(json.dumps(_plan(self.base, "report.csv", sha)), encoding="utf-8")
        self.assertEqual(ec.main(["--plan", str(bad_now), "--now", "naiv"]), 2)


if __name__ == "__main__":
    unittest.main()

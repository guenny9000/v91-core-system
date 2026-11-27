"""Tests fuer controller/baseline_register.py (Stufe-D-Baseline-Register).

Selbst-contained: nur stdlib + tempfile, kein Netz, keine Fremddateien
(#524-Dauerregel: Tests duerfen keine Dateien ausserhalb tempfile nutzen).
Alle Gates werden UEBER die REUSE-Bausteine aus impact.py geprueft.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import baseline_register as br  # noqa: E402


def reihe(start_tag, werte, quelle="direct_sensor"):
    """tz-bewusste Messreihe bauen (stundenaufgeloest, +01:00)."""
    return [
        {
            "timestamp": "2026-11-%02dT%02d:00:00+01:00" % (start_tag, stunde),
            "value": float(wert),
            "source_type": quelle,
        }
        for stunde, wert in enumerate(werte)
    ]


class BaselineRegisterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pfad = str(pathlib.Path(self._tmp.name) / "register.jsonl")
        self.basis = reihe(20, [100, 98, 101, 99, 100, 97])
        self.besser = reihe(25, [80, 79, 81, 78, 80, 77])

    def tearDown(self):
        self._tmp.cleanup()

    def registriere(self, **kwargs):
        standard = dict(
            register_path=self.pfad,
            kennzahl="pumpenleistung",
            unit="kW",
            higher_is_worse=True,
            baseline_rows=self.basis,
            systemgrenze="gebaeude-a:pumpe-01",
        )
        standard.update(kwargs)
        return br.register_baseline(**standard)

    def vergleiche(self, **kwargs):
        standard = dict(
            register_path=self.pfad,
            kennzahl="pumpenleistung",
            after_rows=self.besser,
            systemgrenze="gebaeude-a:pumpe-01",
        )
        standard.update(kwargs)
        return br.vergleiche_gegen_baseline(**standard)

    # --- Registrierung -------------------------------------------------
    def test_register_erfolgreich_und_append(self):
        ergebnis = self.registriere()
        self.assertEqual(ergebnis["status"], br.BASELINE_REGISTRIERT)
        self.assertEqual(ergebnis["n_baseline"], 6)
        self.assertGreater(ergebnis["dqi"], 0.85)
        eintraege = br._lade_eintraege(self.pfad)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["schema_version"], br.VERSION)
        self.assertEqual(eintraege[0]["unit"], "kW")
        self.assertEqual(eintraege[0]["systemgrenze"], "gebaeude-a:pumpe-01")

    def test_zu_wenig_baseline_samples_nichts_geschrieben(self):
        ergebnis = self.registriere(baseline_rows=self.basis[:2], min_samples=5)
        self.assertEqual(ergebnis["status"], br.NICHT_REGISTRIERT)
        self.assertIn("TOO_FEW_BASELINE_SAMPLES", ergebnis["gruende"])
        self.assertFalse(pathlib.Path(self.pfad).exists())

    def test_low_dqi_nichts_geschrieben(self):
        manuell = reihe(20, [100, 98, 101, 99, 100], quelle="manual_entry")
        ergebnis = self.registriere(baseline_rows=manuell)
        self.assertEqual(ergebnis["status"], br.NICHT_REGISTRIERT)
        self.assertIn("LOW_DQI", ergebnis["gruende"])
        self.assertFalse(pathlib.Path(self.pfad).exists())

    def test_naive_zeitstempel_werden_abgelehnt(self):
        naiv = [
            {"timestamp": "2026-11-20T%02d:00:00" % stunde, "value": 100.0,
             "source_type": "direct_sensor"}
            for stunde in range(6)
        ]
        ergebnis = self.registriere(baseline_rows=naiv)
        self.assertEqual(ergebnis["status"], br.NICHT_REGISTRIERT)
        self.assertEqual(ergebnis["abgewiesen"], 6)

    def test_doppelte_kennzahl_neuester_gilt(self):
        self.registriere()
        zweite = self.registriere(
            baseline_rows=reihe(22, [50, 49, 51, 50, 48, 52]),
            unit="kW",
        )
        self.assertEqual(zweite["status"], br.BASELINE_REGISTRIERT)
        eintraege = br._lade_eintraege(self.pfad)
        self.assertEqual(len(eintraege), 2)
        vergleich = self.vergleiche()
        # Gegen die NEUESTE Baseline (Mittel ~50) ist die Nachher-Reihe
        # schlechter statt besser: higher_is_worse=True, Nachher > Baseline.
        self.assertEqual(vergleich["status"], "NO_IMPROVEMENT")

    def test_register_ist_append_only(self):
        self.registriere()
        vorher = pathlib.Path(self.pfad).read_text(encoding="utf-8")
        self.registriere(baseline_rows=reihe(22, [50, 49, 51, 50, 48, 52]))
        nachher = pathlib.Path(self.pfad).read_text(encoding="utf-8")
        self.assertTrue(nachher.startswith(vorher))
        self.assertEqual(len(nachher.strip().splitlines()), 2)

    def test_meta_felder_fail_closed(self):
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(kennzahl="")
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(systemgrenze="  ")
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(higher_is_worse="ja")

    def test_calibration_ref_grenzen(self):
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(calibration_ref="x" * 2049)
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(calibration_ref="   ")
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(calibration_status="ERFUNDEN")
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(calibration_status="REFERENCE_PRESENT_NOT_VERIFIED")
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(
                calibration_ref="ledger:kal-2026-11",
                calibration_status="MISSING_REFERENCE",
            )
        ok = self.registriere(
            calibration_ref="ledger:kal-2026-11",
            calibration_status="REFERENCE_PRESENT_NOT_VERIFIED",
        )
        self.assertEqual(ok["status"], br.BASELINE_REGISTRIERT)

    def test_thresholds_werden_aufgezeichnet(self):
        ergebnis = self.registriere(min_samples=3, dqi_min=0.5, noise_factor=1.5)
        self.assertEqual(ergebnis["thresholds"]["min_samples"], 3)
        self.assertEqual(ergebnis["thresholds"]["dqi_min"], 0.5)
        self.assertEqual(ergebnis["thresholds"]["noise_factor"], 1.5)
        with self.assertRaises(ValueError):
            self.registriere(min_samples=1)
        with self.assertRaises(ValueError):
            self.registriere(dqi_min=0.0)

    def test_kaputte_register_zeile_stoppt(self):
        self.registriere()
        with pathlib.Path(self.pfad).open("a", encoding="utf-8") as handle:
            handle.write("{kein json\n")
        with self.assertRaises(br.BaselineRegisterError):
            br._lade_eintraege(self.pfad)
        # Registrierung schreibt NICHT in ein kaputtes Register.
        with self.assertRaises(br.BaselineRegisterError):
            self.registriere(kennzahl="weitere")

    # --- Vergleich -----------------------------------------------------
    def test_vergleich_valid_nach_besserer_reihe(self):
        self.registriere()
        vergleich = self.vergleiche()
        self.assertEqual(vergleich["status"], "VALID")
        self.assertGreater(vergleich["vergleich"]["saved_per_sample"], 0)
        self.assertEqual(vergleich["vergleich"]["thresholds"]["min_samples"], 5)
        self.assertEqual(
            vergleich["kalibrierung"]["calibration_status"], None
        )

    def test_vergleich_no_improvement(self):
        self.registriere()
        schlechter = reihe(25, [110, 112, 111, 113, 110, 114])
        vergleich = self.vergleiche(after_rows=schlechter)
        self.assertEqual(vergleich["status"], "NO_IMPROVEMENT")
        self.assertLess(vergleich["vergleich"]["saved_per_sample"], 0)

    def test_vergleich_quarantine_zu_wenig_nachher(self):
        self.registriere()
        vergleich = self.vergleiche(after_rows=self.besser[:2])
        self.assertEqual(vergleich["status"], "QUARANTINE")
        self.assertIn("TOO_FEW_SAMPLES", vergleich["gruende"])

    def test_vergleich_temporal_error_uebernommen(self):
        self.registriere()
        # Nachher beginnt VOR dem Baseline-Ende -> impact.py TEMPORAL_ERROR.
        frueh = reihe(19, [80, 79, 81, 78, 80, 77])
        vergleich = self.vergleiche(after_rows=frueh)
        self.assertEqual(vergleich["status"], "QUARANTINE")
        self.assertIn("TEMPORAL_ERROR", vergleich["gruende"])

    def test_vergleich_unbekannte_kennzahl(self):
        self.registriere()
        vergleich = self.vergleiche(kennzahl="gibts-nicht")
        self.assertEqual(vergleich["status"], br.NICHT_GEFUNDEN)
        self.assertIn("KENNZAHL_NICHT_IM_REGISTER", vergleich["gruende"])

    def test_vergleich_systemgrenze_abweichend(self):
        self.registriere()
        vergleich = self.vergleiche(systemgrenze="gebaeude-b:pumpe-07")
        self.assertEqual(vergleich["status"], br.NICHT_VERGLEICHBAR)
        self.assertIn("SYSTEMGRENZE_ABWEICHEND", vergleich["gruende"])

    def test_vergleich_workload_einheit_abweichend(self):
        self.registriere(workload_einheit="stueck")
        vergleich = self.vergleiche(workload_einheit="stunde")
        self.assertEqual(vergleich["status"], br.NICHT_VERGLEICHBAR)
        self.assertIn("WORKLOAD_EINHEIT_ABWEICHEND", vergleich["gruende"])
        passthrough = self.vergleiche(workload_einheit="stueck")
        self.assertEqual(passthrough["status"], "VALID")

    def test_vergleichveraendert_register_nicht(self):
        self.registriere()
        vorher = pathlib.Path(self.pfad).read_bytes()
        self.vergleiche()
        self.vergleiche(systemgrenze="falsch")
        self.vergleiche(kennzahl="gibts-nicht")
        self.assertEqual(pathlib.Path(self.pfad).read_bytes(), vorher)

    def test_vergleich_richtung_hoeher_besser(self):
        # Kennzahl, bei der HOEHERE Werte besser sind (z. B. Wirkungsgrad).
        ergebnis = br.register_baseline(
            self.pfad, "wirkungsgrad", "prozent", False,
            reihe(20, [60, 61, 59, 60, 62, 60]), "anlage-x:eta",
        )
        self.assertEqual(ergebnis["status"], br.BASELINE_REGISTRIERT)
        besser = reihe(25, [70, 71, 69, 70, 72, 70])
        vergleich = br.vergleiche_gegen_baseline(
            self.pfad, "wirkungsgrad", besser, "anlage-x:eta"
        )
        self.assertEqual(vergleich["status"], "VALID")


class BaselineRegisterCLITest(unittest.TestCase):
    """CLI-E2E: exit 0/1/2, CSV-Import REUSE impact.load_csv."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = pathlib.Path(self._tmp.name)
        self.register = str(self.wurzel / "register.jsonl")
        self.modul = str(
            pathlib.Path(__file__).resolve().parents[1] / "controller" / "baseline_register.py"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _csv(self, name, werte, tag):
        pfad = self.wurzel / name
        zeilen = ["timestamp,value,source_type"]
        for stunde, wert in enumerate(werte):
            zeilen.append(
                "2026-11-%02dT%02d:00:00+01:00,%s,direct_sensor" % (tag, stunde, wert)
            )
        pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return str(pfad)

    def _lauf(self, *argumente):
        prozess = subprocess.run(
            [sys.executable, self.modul, *argumente],
            capture_output=True, text=True, timeout=120,
        )
        return prozess.returncode, prozess.stdout, prozess.stderr

    def test_self_check_exit_0(self):
        code, ausgabe, _ = self._lauf("--self-check")
        self.assertEqual(code, 0)
        self.assertIn("NICHT_GEPRUEFT", ausgabe)

    def test_register_und_vergleich_ueber_cli(self):
        csv_basis = self._csv("basis.csv", [100, 98, 101, 99, 100, 97], 20)
        code, ausgabe, _ = self._lauf(
            "--register", self.register, "--kennzahl", "pumpenleistung",
            "--unit", "kW", "--systemgrenze", "gebaeude-a:pumpe-01",
            "--csv", csv_basis,
        )
        self.assertEqual(code, 0)
        self.assertIn(br.BASELINE_REGISTRIERT, ausgabe)
        csv_nachher = self._csv("nachher.csv", [80, 79, 81, 78, 80, 77], 25)
        code, ausgabe, _ = self._lauf(
            "--vergleiche", self.register, "--kennzahl", "pumpenleistung",
            "--systemgrenze", "gebaeude-a:pumpe-01", "--csv", csv_nachher,
        )
        self.assertEqual(code, 0)
        self.assertIn("VALID", ausgabe)

    def test_cli_nicht_vergleichbar_exit_1(self):
        csv_basis = self._csv("basis.csv", [100, 98, 101, 99, 100, 97], 20)
        self._lauf(
            "--register", self.register, "--kennzahl", "pumpenleistung",
            "--unit", "kW", "--systemgrenze", "gebaeude-a:pumpe-01",
            "--csv", csv_basis,
        )
        csv_nachher = self._csv("nachher.csv", [80, 79, 81, 78, 80, 77], 25)
        code, ausgabe, _ = self._lauf(
            "--vergleiche", self.register, "--kennzahl", "pumpenleistung",
            "--systemgrenze", "andere-grenze", "--csv", csv_nachher,
        )
        self.assertEqual(code, 1)
        self.assertIn(br.NICHT_VERGLEICHBAR, ausgabe)

    def test_cli_fehler_exit_2(self):
        code, ausgabe, _ = self._lauf(
            "--register", self.register, "--kennzahl", "",
            "--unit", "kW", "--systemgrenze", "g",
            "--csv", self._csv("b.csv", [1, 2, 3, 4, 5, 6], 20),
        )
        self.assertEqual(code, 2)
        self.assertIn("fehler", ausgabe)


if __name__ == "__main__":
    unittest.main()

"""Pruef-Protokoll-Tests fuer die MAX-BEST-Datenbruecke (echte Module).

Deckt die Protokoll-Zeilen TF-IMP-01..04, TF-RAD-01..03, TF-ALM-02 soweit
auf der Bruecke lieferbar ab - ALLE gegen die ECHTEN Module impact.py,
legacy_radar.py, max_best_rechner.py (KEINE MOCK-RECHNUNG).
"""
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# gleiche Pfadregel wie test_impact.py: impact.py importiert 'ledger'
sys.path.insert(0, str(ROOT / "controller"))

from controller import impact
from controller import max_best_rechner
from controller import legacy_radar
from controller.max_best_datenbruecke import (
    CONSTRAINTS, csv_nutzen, radar_risiko, rechnen, HONESTY_LIMITS)


def _csv(path, rows):
    path.write_text("timestamp,value,source_type\n" + "\n".join(rows) + "\n",
                    encoding="utf-8")


def valid_rows(start="2026-11-01T", hour=0, value=10.0, n=6):
    return ["%s%02d:00:00+01:00,%.2f,direct_sensor" % (start, hour + i, value)
            for i in range(n)]


def valid_lifecycle():
    return {
        "dependency_map": "two deps, docs/depmap.md",
        "risk_assessment": "low, docs/risk.md",
        "migration_plan": "move to open standard replacement",
        "rollback": "reinstall prior version via package cache",
        "continuity_checks": "service check plus smoke test",
    }


def valid_component(**overrides):
    base = {
        "component_id": "CMP-001",
        "kind": "software",
        "name": "example-package",
        "owner": "operator@example",
        "evidence": {"source": "repo lockfile", "checked_on": "2026-11-21"},
        "eol_status": "supported",
        "in_active_use": True,
        "lifecycle": valid_lifecycle(),
    }
    base.update(overrides)
    return base


def inventory_with(components):
    return {
        "node_id": "node-alpha",
        "date": "2026-11-24",
        "reviewer": "vibe",
        "components": components,
    }


class TFImp(unittest.TestCase):
    """TF-IMP-01..04: echte CSV-Messreihe -> Rechner."""

    def test_tf_imp_01_valid_csv(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "base.csv"
            a = Path(d) / "after.csv"
            _csv(b, valid_rows(value=10.0))
            _csv(a, ["2026-11-08T%02d:00:00+01:00,6.00,direct_sensor" % i
                     for i in range(6)])
            br = csv_nutzen(str(b), str(a), "kWh",
                            ziel="VB-ENERGIE-01 last senken",
                            verantwortlicher="sebastian",
                            zeitraum="2026-11-01..2026-11-08",
                            measure="bruecke-test", min_samples=2,
                            dqi_min=0.5, noise_factor=0.1,
                            schaden=0.0, aufwand=1.0)
            erg = rechnen(br)
        self.assertEqual(erg["results"]["gesamtnutzen"]["status"],
                         "BERECHNET")
        nutzen = erg["results"]["gesamtnutzen"]["wert"]
        # Handrechnung: saved 10-6=4; U = 4 - 0 - 1 = 3
        self.assertTrue(math.isclose(nutzen, 3.0, rel_tol=1e-9))
        self.assertEqual(erg["bilanz"]["formeln"], 1)
        self.assertEqual(erg["bilanz"]["nicht_geprueft"], 0)

    def test_tf_imp_02_fehlender_wert_nicht_geprueft_kein_null(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "base.csv"
            _csv(b, valid_rows(value=10.0))
            a = Path(d) / "after.csv"
            # 2 gueltige + 3 unbrauchbare Zeilen -> DQI faellt, QUARANTINE
            rows = ["2026-11-08T%02d:00:00+01:00,6.00,direct_sensor" % i
                    for i in range(2)]
            rows += ["2026-11-08T%02d:00:00+01:00" % (2 + i) for i in range(3)]
            _csv(a, rows)
            br = csv_nutzen(str(b), str(a), "kWh", "z", "v", "p",
                            measure="bruecke-test", min_samples=2,
                            dqi_min=0.5, noise_factor=0.1)
            erg = rechnen(br)
        self.assertEqual(erg["results"]["gesamtnutzen"]["status"],
                         "NICHT_GEPRUEFT")
        self.assertIsNone(erg["results"]["gesamtnutzen"]["wert"])
        self.assertEqual(erg["bilanz"]["nicht_geprueft"], 1)

    def test_tf_imp_03_domainverletzung_fail_closed(self):
        with self.assertRaises(max_best_rechner.MaxBestInputError):
            max_best_rechner.risiko(1.5, 100.0)
        with self.assertRaises(max_best_rechner.MaxBestInputError):
            max_best_rechner.gesamtnutzen(-1.0, 0.0, 0.0)
        with self.assertRaises(Exception):
            # ungueltige co2-Kombination im ECHTEN impact-Modul
            impact.compute_impact("x", [{"timestamp": "2026-01-01T00:00:00+01:00",
                                         "value": "1", "source_type": "sensor"}] * 3,
                                   [{"timestamp": "2026-02-01T00:00:00+01:00",
                                     "value": "1", "source_type": "sensor"}] * 3,
                                   "kg", co2_factor_kg_per_unit=0.5,
                                   co2_source="  ")

    def test_tf_imp_04_annahme_bleibt_gekennzeichnet(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "base.csv"
            a = Path(d) / "after.csv"
            _csv(b, valid_rows(value=10.0))
            _csv(a, ["2026-11-08T%02d:00:00+01:00,7.00,direct_sensor" % i
                     for i in range(6)])
            br = csv_nutzen(str(b), str(a), "kWh", "z", "v", "p",
                            annahme=True, measure="bruecke-test",
                            min_samples=2, dqi_min=0.5, noise_factor=0.1,
                            schaden=0.0, aufwand=1.0)
            erg = rechnen(br)
        self.assertTrue(erg["meta"]["annahme"])
        self.assertIn("quelle", erg["meta"])
        self.assertNotIn("MESSUNG", str(erg["meta"]))
        # ANNAHME veraendert die Zahl NICHT (Gleichbehandlung), nur meta:
        self.assertEqual(erg["results"]["gesamtnutzen"]["status"],
                         "BERECHNET")
        self.assertTrue(math.isclose(erg["results"]["gesamtnutzen"]["wert"],
                                      2.0, rel_tol=1e-9))


class TFRad(unittest.TestCase):
    """TF-RAD-01..03: echter Radar-Bericht -> Risiko-Auftrag."""

    def test_tf_rad_01_mit_betreiber_werten_handrechnung(self):
        inv = inventory_with([valid_component(
            component_id="CMP-A", eol_status="isolate"),
            valid_component(component_id="CMP-B", eol_status="replace")])
        br = radar_risiko(inv, {"CMP-A": 0.2, "CMP-B": 0.4},
                          {"CMP-A": 100.0, "CMP-B": 200.0},
                          ziel="strukturrisiken senken",
                          verantwortlicher="sebastian", zeitraum="Q4-2026")
        erg = rechnen(br)
        self.assertEqual(erg["results"]["risiko"]["status"], "BERECHNET")
        # Handrechnung: p-Mittel (0.2+0.4)/2 = 0.3, S-Mittel (100+200)/2 = 150,
        # Risiko = 0.3 * 150 = 45.0 (Betreiber-ANGABEN, keine Messung)
        self.assertTrue(math.isclose(erg["results"]["risiko"]["wert"],
                                      45.0, rel_tol=1e-9))
        self.assertEqual(erg["results"]["restrisiko"]["status"],
                         "NICHT_GEPRUEFT")
        self.assertEqual(erg["meta"]["items_gesamt"], 2)
        self.assertFalse(erg["meta"]["annahme"])  # Betreiberangaben != ANN.

    def test_tf_rad_02_ohne_pruefwert_nicht_geprueft(self):
        inv = inventory_with([valid_component(
            component_id="CMP-A", eol_status="unknown")])
        br = radar_risiko(inv, ziel="z", verantwortlicher="v",
                          zeitraum="p")
        erg = rechnen(br)
        self.assertEqual(erg["results"]["risiko"]["status"],
                         "NICHT_GEPRUEFT")
        self.assertIsNone(erg["results"]["risiko"]["wert"])
        self.assertEqual(erg["meta"]["radar_state"],
                         "RADAR_REPORTED_COMPLETE")

    def test_tf_rad_03_teilversorgt_bleibt_nicht_geprueft(self):
        inv = inventory_with([valid_component(
            component_id="CMP-A", eol_status="isolate"),
            valid_component(component_id="CMP-B", eol_status="replace")])
        br = radar_risiko(inv, {"CMP-A": 0.2})
        erg = rechnen(br)
        self.assertEqual(erg["results"]["risiko"]["status"],
                         "NICHT_GEPRUEFT")

    def test_tf_rad_03_output_trennung(self):
        inv = inventory_with([valid_component(
            component_id="CMP-A", eol_status="isolate")])
        br = radar_risiko(inv, {"CMP-A": 0.5}, {"CMP-A": 10.0})
        erg = rechnen(br)
        self.assertIn("results", erg)
        self.assertIn("constraints", erg)
        self.assertIn("meta", erg)
        # Zahlen NUR in results; constraints enthaelt NIE Zahlenwerte
        for v in erg["constraints"].values():
            if isinstance(v, bool):
                self.assertTrue(v)
            else:
                self.assertIsInstance(v, str)
        self.assertIn("menschenwuerde_vorrang", erg["constraints"])
        # unbekannter Formelbereich bleibt fail-closed beim Rechner:
        with self.assertRaises(max_best_rechner.MaxBestInputError):
            max_best_rechner.berechne({"erfinden": {}})


class TFAlm(unittest.TestCase):
    """TF-ALM-02 soweit auf der Bruecke lieferbar: fehlender Messwert
    loest KEINE Zahl aus. Voller Schwellwert-Alarm gehoert zum offenen
    PR #520 und ist hier NICHT behauptet."""

    def test_tf_alm_02_kein_alarm_aus_nicht_geprueft(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "base.csv"
            a = Path(d) / "after.csv"
            _csv(b, valid_rows(value=1.0))
            _csv(a, valid_rows(value=1.0))
            br = csv_nutzen(str(b), str(a), "kWh", "z", "v", "p",
                            measure="bruecke-test", min_samples=2,
                            dqi_min=0.5, noise_factor=0.1)
            erg = rechnen(br)
        # NO_IMPROVEMENT ist KEIN VALID -> NICHT_GEPRUEFT, keine Zahl:
        self.assertEqual(erg["results"]["gesamtnutzen"]["status"],
                         "NICHT_GEPRUEFT")
        ohne_zahl = [k for k, v in erg["results"].items()
                     if k != "bilanz"
                     and v["status"] == "NICHT_GEPRUEFT"]
        self.assertTrue(ohne_zahl)

    def test_honesty_limits_und_constraints_statisch(self):
        self.assertIn("RECHNEN != ENTSCHEIDEN", HONESTY_LIMITS)
        self.assertIn("UNKNOWN != PASS", HONESTY_LIMITS)
        static = dict(CONSTRAINTS)
        self.assertIn("hinweis", static)


if __name__ == "__main__":
    unittest.main()

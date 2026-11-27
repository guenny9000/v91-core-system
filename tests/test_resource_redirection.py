"""Tests fuer den Resource-Redirection- & Wirkungsrechner
(V91-CONTRIB-2026-11-27-RRR, FREMD-ENTWURF nach Nachmessung).

Verriegelt: Status-Trennung FAKT/ANNAHME/NICHT_GEPRUEFT, Fail-Closed
bei FAKT ohne Messwert/Quelle, Sozialpuffer VOR Verteilung,
Sektor-Validierung, ANNAHME-Referenz nach der FOES-Nachmessung
(KEINE Uebernahme der unbestaetigten 43-Mrd-Zahl des Entwurfs),
RECHENMODELL != HAUSHALT.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import resource_redirection as rr  # noqa: E402


def _fakt_massnahme(**overrides):
    basis = dict(
        massnahme_id="V91-WIRK-0001",
        bereich="Wasser & Biodiversitaet",
        titel="Regenwasserspeicherung Alsfeld-Node",
        mittel_eur=1200.0,
        erwartete_wirkung_einheit="Liter Speichervolumen",
        zielwert=500.0,
        ist_wert=120.0,
        status="FAKT",
        quelle="Lokale Zaehlerablesung Node-1",
        soziale_absicherung="Offenes Gemeinschaftsmodul",
        tags=("wasser", "alsfeld"),
    )
    basis.update(overrides)
    return rr.WirkungsMassnahme(**basis)


class WirkungsbilanzTest(unittest.TestCase):
    def test_bilanz_trennt_fakt_annahme_und_nicht_geprueft(self):
        liste = [
            _fakt_massnahme(),
            rr.WirkungsMassnahme(
                massnahme_id="V91-WIRK-0002",
                bereich="Kreislaufwirtschaft & Qualifizierung",
                titel="Regionales Reparaturmodul",
                mittel_eur=25000.0,
                erwartete_wirkung_einheit="Reparierte Geraete / Jahr",
                zielwert=400.0,
                ist_wert=None,
                status="NICHT_GEPRUEFT",
                soziale_absicherung="Tarifnahe Qualifizierungsstellen",
                tags=("reparatur", "arbeit"),
            ),
        ]
        bericht = json.loads(rr.berechne_wirkungsbilanz(liste))
        self.assertEqual(bericht["schema_version"], "v91-resource-redirection-1.0")
        self.assertEqual(bericht["gesamt_mittel_eur"], 26200.0)
        self.assertEqual(bericht["belegte_mittel_eur"], 1200.0)
        self.assertEqual(bericht["ungepruefte_oder_annahme_mittel_eur"], 25000.0)
        self.assertEqual(bericht["eintraege"][0]["erfuellungsgrad"], 0.24)
        self.assertIsNone(bericht["eintraege"][1]["erfuellungsgrad"])

    def test_fail_closed_bei_fakt_ohne_messwert(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(ist_wert=None)

    def test_fail_closed_bei_fakt_ohne_quelle(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(quelle="   ")

    def test_annahme_erfordert_benannte_annahme(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(
                status="ANNAHME", ist_wert=None, quelle="",
            )

    def test_unzulaessiger_status_fail_closed(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(status="GESCHAETZT")

    def test_negative_mittel_und_zielwert_fail_closed(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_eur=-1.0)
        with self.assertRaises(ValueError):
            _fakt_massnahme(zielwert=0.0)


class UmleitungTest(unittest.TestCase):
    def test_sozialpuffer_und_modulverteilung_nach_foes_referenz(self):
        res = rr.standard_szenario_beispiel()
        # 38,4 Mrd * 10 % = 3,84 Mrd brutto; 35 % Sozialpuffer = 1,344 Mrd
        self.assertEqual(res["brutto_umleitung_eur"], 3_840_000_000.0)
        self.assertEqual(res["sozial_absicherung_eur"], 1_344_000_000.0)
        self.assertEqual(res["netto_projekt_budget_eur"], 2_496_000_000.0)

        module = res["module"]
        self.assertEqual(len(module), 3)
        self.assertEqual(module[0]["budget_eur"], 998_400_000.0)
        self.assertEqual(module[0]["einheiten"], 66560.0)
        # Wasser-Modul: 873,6 Mio / 2,50 EUR je m3
        self.assertEqual(module[1]["budget_eur"], 873_600_000.0)
        self.assertEqual(module[1]["einheiten"], 349_440_000.0)
        # Kreislauf-Modul: 624 Mio / 45.000 EUR je Platzjahr
        self.assertEqual(module[2]["budget_eur"], 624_000_000.0)
        self.assertEqual(module[2]["einheiten"], 13866.67)

    def test_referenz_ist_foes_nicht_die_unbestaetigte_43_mrd(self):
        res = rr.standard_szenario_beispiel()
        self.assertIn("FOES", res["referenz"])
        self.assertIn("38,4 Mrd", res["referenz"])
        quelle = json.dumps(res, ensure_ascii=False)
        self.assertNotIn("43 Mrd", quelle)  # EEA-43-Mrd-Zahl NICHT uebernommen

    def test_fail_closed_bei_fakt_ohne_nachweis(self):
        with self.assertRaises(ValueError):
            rr.UmleitungsQuelle(
                quelle_id="Q-ERR",
                bezeichnung="Unbelegter Fakt",
                basis_subvention_eur=1_000_000.0,
                abbau_anteil=0.2,
                sozial_absicherung_anteil=0.2,
                status="FAKT",
                nachweis="",
            )

    def test_sektor_validierung_nachgetragen(self):
        with self.assertRaises(ValueError):
            rr.ZielModul(
                modul_id="M-ERR",
                sektor="MILITAER",  # nicht in der Skala (RagnaroeK)
                titel="Ungueltig",
                kosten_pro_einheit_eur=100.0,
                wirkung_einheit="x",
                gewichtung_anteil=0.5,
                status="NICHT_GEPRUEFT",
            )

    def test_annahme_modul_erfordert_nachweis(self):
        with self.assertRaises(ValueError):
            rr.ZielModul(
                modul_id="M-ERR",
                sektor="WASSER",
                titel="Unbelegte Annahme",
                kosten_pro_einheit_eur=100.0,
                wirkung_einheit="x",
                gewichtung_anteil=0.5,
                status="ANNAHME",
                nachweis="",
            )

    def test_anteile_ausserhalb_0_1_fail_closed(self):
        with self.assertRaises(ValueError):
            rr.UmleitungsQuelle(
                quelle_id="Q-ERR", bezeichnung="x",
                basis_subvention_eur=10.0, abbau_anteil=1.5,
                sozial_absicherung_anteil=0.2, status="ANNAHME", nachweis="n",
            )
        with self.assertRaises(ValueError):
            rr.UmleitungsQuelle(
                quelle_id="Q-ERR", bezeichnung="x",
                basis_subvention_eur=10.0, abbau_anteil=0.1,
                sozial_absicherung_anteil=-0.2, status="ANNAHME", nachweis="n",
            )

    def test_leere_modulliste_und_nullgewichte_fail_closed(self):
        q = rr.UmleitungsQuelle(
            quelle_id="Q1", bezeichnung="x", basis_subvention_eur=10.0,
            abbau_anteil=0.1, sozial_absicherung_anteil=0.2,
            status="ANNAHME", nachweis="n",
        )
        with self.assertRaises(ValueError):
            rr.berechne_umleitung([q], [])
        m0 = rr.ZielModul(
            modul_id="M0", sektor="WASSER", titel="t",
            kosten_pro_einheit_eur=10.0, wirkung_einheit="m3",
            gewichtung_anteil=0.0, status="NICHT_GEPRUEFT",
        )
        with self.assertRaises(ValueError):
            rr.berechne_umleitung([q], [m0])

    def test_sozialpuffer_wird_vor_verteilung_abgezogen(self):
        q = rr.UmleitungsQuelle(
            quelle_id="Q1", bezeichnung="x", basis_subvention_eur=100.0,
            abbau_anteil=1.0, sozial_absicherung_anteil=0.5,
            status="ANNAHME", nachweis="n",
        )
        m = rr.ZielModul(
            modul_id="M0", sektor="WASSER", titel="t",
            kosten_pro_einheit_eur=10.0, wirkung_einheit="m3",
            gewichtung_anteil=1.0, status="NICHT_GEPRUEFT",
        )
        res = rr.berechne_umleitung([q], [m])
        self.assertEqual(res["brutto_umleitung_eur"], 100.0)
        self.assertEqual(res["sozial_absicherung_eur"], 50.0)
        self.assertEqual(res["module"][0]["budget_eur"], 50.0)  # SOZIAL_SCHUTZ_VOR_PROJEKT


class CliTest(unittest.TestCase):
    def test_beispiel_exit_zero_und_referenz(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            with out.open("w") as handle:
                code = subprocess.run(
                    [sys.executable, "-m", "controller.resource_redirection", "--beispiel"],
                    stdout=handle, stderr=subprocess.PIPE, text=True, timeout=60,
                    cwd=str(Path(__file__).resolve().parents[1]),
                ).returncode
            self.assertEqual(code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("FOES", data["referenz"])

    def test_eingabe_und_ungueltiges_szenario(self):
        root = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as tmp:
            sz = Path(tmp) / "s.json"
            sz.write_text(json.dumps({
                "quellen": [{
                    "quelle_id": "Q1", "bezeichnung": "x",
                    "basis_subvention_eur": 100.0, "abbau_anteil": 1.0,
                    "sozial_absicherung_anteil": 0.5, "status": "ANNAHME",
                    "nachweis": "n",
                }],
                "module": [{
                    "modul_id": "M0", "sektor": "WASSER", "titel": "t",
                    "kosten_pro_einheit_eur": 10.0, "wirkung_einheit": "m3",
                    "gewichtung_anteil": 1.0, "status": "NICHT_GEPRUEFT",
                }],
            }), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "-m", "controller.resource_redirection", "--eingabe", str(sz)],
                capture_output=True, text=True, timeout=60, cwd=root,
            )
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["netto_projekt_budget_eur"], 50.0)

            bad = Path(tmp) / "bad.json"
            bad.write_text('{"quellen": [{"quelle_id": "Q"}]}', encoding="utf-8")
            r2 = subprocess.run(
                [sys.executable, "-m", "controller.resource_redirection", "--eingabe", str(bad)],
                capture_output=True, text=True, timeout=60, cwd=root,
            )
            self.assertEqual(r2.returncode, 1)
            self.assertIn("Fail-Closed", r2.stdout)


if __name__ == "__main__":
    unittest.main()

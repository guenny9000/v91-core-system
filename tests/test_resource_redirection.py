"""Tests fuer den Resource-Redirection- & Wirkungsrechner
(V91-CONTRIB-2026-11-27-RRR, FREMD-ENTWURF nach Nachmessung).

Verriegelt: Status-Trennung FAKT/ANNAHME/NICHT_GEPRUEFT, Fail-Closed
bei FAKT ohne Messwert/Quelle, Sozialpuffer VOR Verteilung,
Sektor-Validierung, ANNAHME-Referenz nach der FOES-Nachmessung
(KEINE Uebernahme der unbestaetigten 43-Mrd-Zahl des Entwurfs),
RECHENMODELL != HAUSHALT.

#626-Regressionen (28.11.2026): Finanz-Evidenz ist getrennt von
Wirkungs-Evidenz. Gemessene Wirkung belegt KEINE Mittel; Mittel-FAKT
erfordert Nachweis UND harte Stufe; NICHT_GEPRUEFTE Quellen bleiben
im Aggregat sichtbar (Gesamt-Label, Status-Summen, IDs);
Modul-Lieferung bleibt NICHT_GEPRUEFT (MODELLIERTE_ALLOKATION !=
GEMESSENE_LIEFERUNG); Mittelstufen jenseits der Berechnung bleiben
None. MITTEL_BERECHNET != MITTEL_BEREITGESTELLT.
"""
import json
import math
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
        mittel_status="FAKT",
        mittel_nachweis="Gemeinde-Haushaltsplan 2026, Position 05 (Mittel-Freigabe)",
        mittel_stufe="TRANSFERIERT",
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
        self.assertEqual(bericht["schema_version"], "v91-resource-redirection-1.1")
        self.assertEqual(bericht["gesamt_mittel_eur"], 26200.0)
        self.assertEqual(bericht["belegte_mittel_eur"], 1200.0)
        self.assertEqual(bericht["annahme_mittel_eur"], 0.0)
        self.assertEqual(bericht["ungepruefte_mittel_eur"], 25000.0)
        self.assertEqual(bericht["eintraege"][0]["erfuellungsgrad"], 0.24)
        self.assertIsNone(bericht["eintraege"][1]["erfuellungsgrad"])
        # Evidenz-Seiten sind je Eintrag getrennt ausgewiesen (#626)
        self.assertEqual(bericht["eintraege"][0]["wirkungs_status"], "FAKT")
        self.assertEqual(bericht["eintraege"][0]["wirkungs_quelle"], "Lokale Zaehlerablesung Node-1")
        self.assertEqual(bericht["eintraege"][0]["mittel_status"], "FAKT")
        self.assertEqual(bericht["eintraege"][0]["mittel_stufe"], "TRANSFERIERT")
        self.assertEqual(bericht["eintraege"][1]["mittel_status"], "NICHT_GEPRUEFT")

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

    def test_non_finite_measurement_numbers_fail_closed(self):
        for field, value in (("mittel_eur", math.nan), ("zielwert", math.inf), ("ist_wert", -math.inf)):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    _fakt_massnahme(**{field: value})
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_eur=True)


class MittelEvidenzTrennungTest(unittest.TestCase):
    """#626: Finanz-Evidenz und Wirkungs-Evidenz sind NICHT austauschbar."""

    def test_gemessene_wirkung_ohne_mittelbeleg_zaehlt_nicht_als_belegte_mittel(self):
        liste = [_fakt_massnahme(mittel_status="NICHT_GEPRUEFT", mittel_nachweis="", mittel_stufe="BERECHNET")]
        bericht = json.loads(rr.berechne_wirkungsbilanz(liste))
        # Wirkung ist gemessen (FAKT, erfuellungsgrad bleibt 0.24) ...
        self.assertEqual(bericht["eintraege"][0]["erfuellungsgrad"], 0.24)
        self.assertEqual(bericht["eintraege"][0]["wirkungs_status"], "FAKT")
        # ... aber die Mittel bleiben NICHT_GEPRUEFT, nicht belegt, nicht 0:
        self.assertEqual(bericht["eintraege"][0]["mittel_status"], "NICHT_GEPRUEFT")
        self.assertEqual(bericht["belegte_mittel_eur"], 0.0)
        self.assertEqual(bericht["ungepruefte_mittel_eur"], 1200.0)
        self.assertEqual(bericht["gesamt_mittel_eur"], 1200.0)

    def test_mittel_fakt_erfordert_nachweis_und_harte_stufe(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_nachweis="   ")
        # BERECHNET ist keine Finanz-Evidenz:
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_stufe="BERECHNET")

    def test_mittel_annahme_erfordert_benannte_annahme(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_status="ANNAHME", mittel_nachweis="  ")

    def test_unzulaessige_mittel_stufe_fail_closed(self):
        with self.assertRaises(ValueError):
            _fakt_massnahme(mittel_stufe="GESCHAETZT")

    def test_mittelstufen_summen_nach_stufe_getrennt(self):
        liste = [
            _fakt_massnahme(),
            _fakt_massnahme(
                massnahme_id="V91-WIRK-0003",
                mittel_eur=800.0,
                mittel_stufe="AUSGEGEBEN",
            ),
            _fakt_massnahme(
                massnahme_id="V91-WIRK-0004",
                mittel_eur=300.0,
                mittel_status="NICHT_GEPRUEFT",
                mittel_nachweis="",
                mittel_stufe="BERECHNET",
            ),
        ]
        bericht = json.loads(rr.berechne_wirkungsbilanz(liste))
        summen = bericht["mittelstufen_summen_eur"]
        self.assertEqual(summen["TRANSFERIERT"], 1200.0)
        self.assertEqual(summen["AUSGEGEBEN"], 800.0)
        self.assertEqual(summen["BERECHNET"], 300.0)
        self.assertEqual(summen["VERFUEGT"], 0.0)
        self.assertEqual(bericht["belegte_mittel_eur"], 2000.0)
        self.assertEqual(bericht["ungepruefte_mittel_eur"], 300.0)


def _quelle(quelle_id, basis, status, nachweis=""):
    return rr.UmleitungsQuelle(
        quelle_id=quelle_id,
        bezeichnung="Quelle " + quelle_id,
        basis_subvention_eur=basis,
        abbau_anteil=0.10,
        sozial_absicherung_anteil=0.50,
        status=status,
        nachweis=nachweis,
    )


def _modul(modul_id="M0", status="NICHT_GEPRUEFT"):
    return rr.ZielModul(
        modul_id=modul_id,
        sektor="WASSER",
        titel="Modul " + modul_id,
        kosten_pro_einheit_eur=10.0,
        wirkung_einheit="m3",
        gewichtung_anteil=1.0,
        status=status,
    )


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

    def test_non_finite_redirection_amounts_and_unit_costs_fail_closed(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(source_amount=value):
                with self.assertRaises(ValueError):
                    rr.UmleitungsQuelle(
                        quelle_id="Q-NONFINITE", bezeichnung="x",
                        basis_subvention_eur=value, abbau_anteil=0.1,
                        sozial_absicherung_anteil=0.2, status="ANNAHME",
                        nachweis="test assumption",
                    )
            with self.subTest(unit_cost=value):
                with self.assertRaises(ValueError):
                    rr.ZielModul(
                        modul_id="M-NONFINITE", sektor="WASSER", titel="x",
                        kosten_pro_einheit_eur=value, wirkung_einheit="m3",
                        gewichtung_anteil=1.0, status="NICHT_GEPRUEFT",
                    )
        with self.assertRaises(ValueError):
            rr.UmleitungsQuelle(
                quelle_id="Q-BOOL", bezeichnung="x", basis_subvention_eur=True,
                abbau_anteil=0.1, sozial_absicherung_anteil=0.2,
                status="ANNAHME", nachweis="test assumption",
            )


class QuellenStatusImAggregatTest(unittest.TestCase):
    """#626: Per-Quelle-Status bleibt im Umleitungs-Ergebnis erhalten."""

    def test_nicht_gepruefte_quelle_dominiert_gesamtlabel(self):
        quellen = [
            _quelle("Q-FAKT", 100.0, "FAKT", "Bundeshaushaltsbericht"),
            _quelle("Q-UNBEKANNT", 900.0, "NICHT_GEPRUEFT"),
        ]
        res = rr.berechne_umleitung(quellen, [_modul()])
        self.assertEqual(res["gesamt_status"], "NICHT_GEPRUEFT")
        self.assertEqual(res["ungepruefte_quellen"], ["Q-UNBEKANNT"])
        self.assertEqual(res["annahme_quellen"], [])
        # Numerische Summen bleiben Szenario-Zahlen, aber je Status getrennt:
        self.assertEqual(res["status_summen"]["FAKT"]["brutto_umleitung_eur"], 10.0)
        self.assertEqual(
            res["status_summen"]["NICHT_GEPRUEFT"]["brutto_umleitung_eur"], 90.0
        )
        self.assertEqual(res["brutto_umleitung_eur"], 100.0)
        # Per-Quelle-Abbildung bleibt vollstaendig:
        self.assertEqual(res["quellen"][0]["status"], "FAKT")
        self.assertEqual(res["quellen"][0]["brutto_umleitung_eur"], 10.0)
        self.assertEqual(res["quellen"][1]["status"], "NICHT_GEPRUEFT")
        self.assertEqual(res["quellen"][1]["brutto_umleitung_eur"], 90.0)

    def test_annahme_quellen_werden_im_aggregat_gelistet(self):
        quellen = [
            _quelle("Q-FAKT", 100.0, "FAKT", "Bundeshaushaltsbericht"),
            _quelle("Q-ANNAHME", 300.0, "ANNAHME", "Modellannahme 30 % Anteil"),
        ]
        res = rr.berechne_umleitung(quellen, [_modul()])
        self.assertEqual(res["gesamt_status"], "ANNAHME")
        self.assertEqual(res["annahme_quellen"], ["Q-ANNAHME"])
        self.assertEqual(res["ungepruefte_quellen"], [])
        # Die benannte Annahme bleibt sichtbar (kein stummer Fakt):
        annahme = [q for q in res["quellen"] if q["quelle_id"] == "Q-ANNAHME"][0]
        self.assertIn("Modellannahme", annahme["nachweis"])
        self.assertEqual(
            res["status_summen"]["ANNAHME"]["brutto_umleitung_eur"], 30.0
        )

    def test_nur_fakt_quellen_erhalten_fakt_gesamtlabel(self):
        res = rr.berechne_umleitung(
            [_quelle("Q-FAKT", 100.0, "FAKT", "Bundeshaushaltsbericht")], [_modul()]
        )
        self.assertEqual(res["gesamt_status"], "FAKT")
        self.assertEqual(res["annahme_quellen"], [])
        self.assertEqual(res["ungepruefte_quellen"], [])

    def test_leere_quellliste_bleibt_nicht_geprueft(self):
        res = rr.berechne_umleitung([], [_modul()])
        self.assertEqual(res["gesamt_status"], "NICHT_GEPRUEFT")
        self.assertEqual(res["brutto_umleitung_eur"], 0.0)

    def test_standardbeispiel_ist_aggregat_annahme(self):
        res = rr.standard_szenario_beispiel()
        self.assertEqual(res["gesamt_status"], "ANNAHME")
        self.assertEqual(res["annahme_quellen"], ["FOSSIL-DE-2024"])
        self.assertEqual(res["szenario_typ"], "MODELLRECHNUNG")


class MittelstufenUndLieferungTest(unittest.TestCase):
    """#626: Berechnete Allokation != verfuegt/transferiert/ausgegeben/verifiziert."""

    def test_mittelstufen_jenseits_der_rechnung_bleiben_none(self):
        res = rr.berechne_umleitung(
            [_quelle("Q1", 100.0, "ANNAHME", "n")], [_modul()]
        )
        stufen = res["mittelstufen"]
        self.assertEqual(stufen["berechnet_eur"], 5.0)
        # RECHNEN != VOLLZUG: keine Stufe wird als 0-Ersatz behauptet:
        self.assertIsNone(stufen["verfuegt_eur"])
        self.assertIsNone(stufen["transferiert_eur"])
        self.assertIsNone(stufen["ausgegeben_eur"])
        self.assertIsNone(stufen["unabhaengig_verifiziert_eur"])
        self.assertIn("MITTEL_BERECHNET != MITTEL_BEREITGESTELLT", res["mittelstufen_hinweis"])
        self.assertIn("RECHNEN != VOLLZUG", res["mittelstufen_hinweis"])

    def test_unbekannte_modullieferung_bleibt_nicht_geprueft(self):
        res = rr.berechne_umleitung(
            [_quelle("Q1", 100.0, "FAKT", "Bundeshaushaltsbericht")],
            [_modul("M-UNBEKANNT", status="NICHT_GEPRUEFT")],
        )
        modul = res["module"][0]
        # Modellierte Schaetzung bleibt numerisch (Szenario) ...
        self.assertEqual(modul["budget_eur"], 5.0)
        self.assertEqual(modul["einheiten"], 0.5)
        self.assertEqual(modul["einheiten_status"], "NICHT_GEPRUEFT")
        # ... aber die LIEFERUNG ist nie gemessen (MODELL != MESSUNG):
        self.assertIsNone(modul["gelieferte_einheiten"])
        self.assertEqual(modul["lieferung_status"], "NICHT_GEPRUEFT")


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

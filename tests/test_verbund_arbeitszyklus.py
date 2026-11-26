"""
Tests fuer controller/verbund_arbeitszyklus.py (unittest, stdlib-only).

Pinnen nach dem Kodex-Muster: Phasenwechsel NUR mit Beleg und genau
eine Stufe, Steueraktionen fail-closed (unbekannter Peer, fehlende
Capability, abgelaufene/widerrufene Identitaet, Policy-Drift, fehlende
Betreiber-Freigabe), KEINE stille Rechteausweitung, UNKNOWN bleibt
UNKNOWN, Peer-Ausfall blockiert lokale Arbeit nicht, ENTSCHEIDUNG !=
VOLLZUG. Wiederverwendung des Alias-Musters: importierte Helper mit
test_*-Praefex werden per Alias importiert, damit pytest sie nicht
als Tests einsammelt.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.verbund_arbeitszyklus import (
    BETREIBER_FREIGABE_PFLICHT,
    PHASEN,
    STEUERAKTIONEN,
    UNBEKANNT,
    VerbundVertragsError,
    audit_eintrag as audit_helfer,
    ergebnis_datensatz as ergebnis_helfer,
    messung_fordert,
    neuer_auftrag,
    pruefe_steueraktion,
    uebergehe_zu,
    verarbeite_statusmeldungen,
    wirksamkeit,
)


def registry(peer_overrides=None):
    """Gueltige Test-Registry: volle Capabilities, nicht abgelaufen."""
    peer = {
        "capabilities": list(STEUERAKTIONEN),
        "gueltig_bis": 2000.0,
        "freigabe_betreiber": True,
    }
    if peer_overrides:
        peer.update(peer_overrides)
    return {"policy_version": "P1", "peers": {"agathon": peer}}


def antrag(aktion="PAUSIEREN", **kwargs):
    basis = {
        "peer_id": "agathon",
        "aktion": aktion,
        "policy_version": "P1",
        "ausloeser": "Messwert ueber Grenze",
        "wirkungsradius": "eine Testkomponente",
        "rollback": "Neustart aus Konfiguration X",
        "jetzt": 100.0,
    }
    basis.update(kwargs)
    return basis


class BestandsPinTest(unittest.TestCase):
    def test_modul_im_bestand(self):
        self.assertTrue((ROOT / "controller" / "verbund_arbeitszyklus.py").exists())

    def test_phasen_und_aktionen_fix(self):
        self.assertEqual(PHASEN, ("ERKANNT", "KOORDINIERT", "AUSGEFUEHRT", "GEMESSEN", "GELERNT"))
        self.assertIn("ABSCHALTEN", STEUERAKTIONEN)
        self.assertEqual(BETREIBER_FREIGABE_PFLICHT, ("ABSCHALTEN", "ERSETZEN"))


class AuftragZyklusTest(unittest.TestCase):
    def test_neuer_auftrag_startet_erkannt(self):
        a = neuer_auftrag("agathon", "Luecke in Doku", "doku")
        self.assertEqual(a["phase"], "ERKANNT")

    def test_neuer_auftrag_fail_closed(self):
        for args in (("", "x", "y"), ("q", "", "y"), ("q", "x", "  ")):
            with self.assertRaises(VerbundVertragsError):
                neuer_auftrag(*args)

    def test_wechsel_nur_eine_stufe_mit_beleg(self):
        a = neuer_auftrag("a", "b", "c")
        b = uebergehe_zu(a, "KOORDINIERT", "Zustaendigkeit verteilt")
        self.assertEqual(b["phase"], "KOORDINIERT")
        self.assertIn("Zustaendigkeit verteilt", b["belege"])

    def test_wechsel_ohne_beleg_abgelehnt(self):
        a = neuer_auftrag("a", "b", "c")
        with self.assertRaises(VerbundVertragsError):
            uebergehe_zu(a, "KOORDINIERT", "  ")

    def test_sprung_und_ruecksprung_abgelehnt(self):
        a = neuer_auftrag("a", "b", "c")
        with self.assertRaises(VerbundVertragsError):
            uebergehe_zu(a, "AUSGEFUEHRT", "zu weit")
        b = uebergehe_zu(a, "KOORDINIERT", "ok")
        with self.assertRaises(VerbundVertragsError):
            uebergehe_zu(b, "ERKANNT", "rueck")

    def test_messung_ohne_datensatz_abgelehnt(self):
        with self.assertRaises(VerbundVertragsError):
            messung_fordert({"phase": "GEMESSEN"})
        messung_fordert({"ergebnis": {"messwert": 1}})


class MessungTest(unittest.TestCase):
    def test_datensatz_felder_vollstaendig(self):
        d = ergebnis_helfer(
            baseline=10, messwert=7, einheit="Ausfaelle/Woche",
            zeitraum="2026-11-20 bis 2026-11-26", quelle="Kernlog",
            unsicherheit=0.5, wirkung=["Grundversorgung"], artefakte=["log.txt"],
        )
        self.assertEqual(d["messwert"], 7)
        self.assertEqual(wirksamkeit(d), "MESSBAR_VERGLICHEN")

    def test_unbekannt_bleibt_unbekannt(self):
        d = ergebnis_helfer(
            baseline=None, messwert=None, einheit="kWh", zeitraum="W1",
            quelle="keine", wirkung=["Ressourcen"], artefakte=[],
        )
        self.assertEqual(d["messwert"], "UNKNOWN")
        self.assertEqual(d["baseline"], "UNKNOWN")
        self.assertEqual(d["unsicherheit"], "UNKNOWN")
        self.assertEqual(wirksamkeit(d), "UNKNOWN")

    def test_datensatz_fail_closed(self):
        with self.assertRaises(VerbundVertragsError):
            ergebnis_helfer(baseline=1, messwert=1, einheit="", zeitraum="W", quelle="q", wirkung=["x"], artefakte=[])
        with self.assertRaises(VerbundVertragsError):
            ergebnis_helfer(baseline=1, messwert=1, einheit="x", zeitraum="W", quelle="q", wirkung=[], artefakte=[])


class SteueraktionTest(unittest.TestCase):
    def test_autorisiert_nur_angefragte_aktion(self):
        e = pruefe_steueraktion(registry(), **antrag())
        self.assertTrue(e["erlaubt"])
        self.assertNotIn("capabilities", e)
        self.assertEqual(e["aktion"], "PAUSIEREN")

    def test_abschalten_ist_isolieren(self):
        e = pruefe_steueraktion(registry(), **antrag(aktion="ABSCHALTEN"))
        self.assertTrue(e["erlaubt"])
        self.assertEqual(e["semantik"], "ISOLIEREN_NICHT_ZERSTOEREN")

    def test_unbekannter_peer_abgelehnt(self):
        e = pruefe_steueraktion(registry(), **antrag(peer_id="fremd"))
        self.assertFalse(e["erlaubt"])
        self.assertIn("nicht registriert", e["grund"])

    def test_unbekannte_aktion_abgelehnt(self):
        e = pruefe_steueraktion(registry(), **antrag(aktion="LOESCHEN"))
        self.assertFalse(e["erlaubt"])

    def test_fehlende_capability_abgelehnt(self):
        e = pruefe_steueraktion(registry({"capabilities": ["PAUSIEREN"]}), **antrag(aktion="ISOLIEREN"))
        self.assertFalse(e["erlaubt"])
        self.assertIn("Capability", e["grund"])

    def test_widerruf_abgelehnt(self):
        e = pruefe_steueraktion(registry({"widerrufen": True}), **antrag())
        self.assertFalse(e["erlaubt"])
        self.assertIn("widerrufen", e["grund"])

    def test_abgelaufen_abgelehnt(self):
        e = pruefe_steueraktion(registry({"gueltig_bis": 50.0}), **antrag(jetzt=100.0))
        self.assertFalse(e["erlaubt"])
        self.assertIn("abgelaufen", e["grund"])

    def test_policy_drift_abgelehnt(self):
        e = pruefe_steueraktion(registry(), **antrag(policy_version="P0"))
        self.assertFalse(e["erlaubt"])
        self.assertIn("Policy", e["grund"])

    def test_betreiber_freigabe_pflicht(self):
        e = pruefe_steueraktion(registry({"freigabe_betreiber": False}), **antrag(aktion="ABSCHALTEN"))
        self.assertFalse(e["erlaubt"])
        self.assertIn("Betreiber-Freigabe", e["grund"])

    def test_rollback_pflicht(self):
        e = pruefe_steueraktion(registry(), **antrag(rollback=" "))
        self.assertFalse(e["erlaubt"])
        self.assertIn("Rollback", e["grund"])

    def test_audit_eintrag_vorhanden(self):
        e = pruefe_steueraktion(registry(), **antrag())
        self.assertIn("VERBUND-AUDIT:", e["audit"])
        daten = json.loads(e["audit"].split("VERBUND-AUDIT:", 1)[1])
        self.assertEqual(daten["aktion"], "PAUSIEREN")

    def test_keine_stille_rechteausweitung(self):
        e = pruefe_steueraktion(registry(), **antrag(aktion="PAUSIEREN"))
        self.assertNotIn("KONFIGURIEREN", json.dumps(e))


class PeerAusfallTest(unittest.TestCase):
    def test_peer_ausfall_blockiert_nicht(self):
        a = neuer_auftrag("agathon", "x", "y")
        ergebnis = verarbeite_statusmeldungen([a], {})
        self.assertEqual(ergebnis[0]["peer_status"], "UNKNOWN")
        self.assertEqual(ergebnis[0]["lokale_arbeit"], "WEITERLAUFEND")

    def test_status_wird_uebernommen(self):
        a = neuer_auftrag("agathon", "x", "y")
        ergebnis = verarbeite_statusmeldungen([a], {"agathon": "LAEUFT"})
        self.assertEqual(ergebnis[0]["peer_status"], "LAEUFT")
        self.assertNotIn("lokale_arbeit", ergebnis[0])


class CliTest(unittest.TestCase):
    def test_self_check(self):
        p = subprocess.run([sys.executable, "controller/verbund_arbeitszyklus.py", "--self-check"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 0)
        self.assertIn("ISOLIEREN_NICHT_ZERSTOEREN", p.stdout)

    def test_ohne_argumente_exit_2(self):
        p = subprocess.run([sys.executable, "controller/verbund_arbeitszyklus.py"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 2)

    def test_alias_import(self):
        self.assertEqual(audit_helfer({"peer_id": "x"})["peer_id"], "x")


if __name__ == "__main__":
    unittest.main()

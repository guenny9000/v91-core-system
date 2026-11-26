"""Tests fuer den Verbund-Peer-Eingang Stufe B (Ende-zu-Ende-
Verbindung von peer_directory + peer_sync + capability_intake,
Vertrag #590 ANHANG Abschnitt 10, Luecken aus PR #599: getrennte
lokale Testinstanzen + Ende-zu-Ende-Verbindung).

Ehrlichkeit: Der Werbungs-Pruefer wird in diesen Tests als Stub
injiziert; der Signatur-Bein ist damit SIMULATION, NICHT
VERIFIZIERT (SIMULATION != VERIFIZIERT). Der echte Ed25519-Bein
laeuft in der CI (cryptography vorhanden) in der separaten Klasse
EchterSignaturBeinTest; lokal ohne cryptography wird er uebersprungen.
KOORDINATION != AUTORISIERUNG != VOLLZUG, INSTANZ != VERBUND.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.peer_directory import PeerDirectory
from controller.peer_sync import PeerRegistry, create_heartbeat
from controller.verbund_peer_eingang import (
    ABGELEHNT,
    AKZEPTIERT,
    BEREIT,
    VERSION,
    VerbundPeerEingangError,
    VerbundInstanz,
)

SECRET_A = bytes(range(32))
SECRET_B = bytes(range(32, 64))
KEY_HEX = "11" * 32


class StubVerdict:
    """Minimaler Ersatz fuer CapabilityVerdict (SIMULATION)."""

    def __init__(self, state, reason="", contributions=None):
        self.state = state
        self.reason = reason
        self.contributions = contributions


def akzeptanz_stub(contributions):
    def pruefer(signed, *, peer_id, directory, now):
        return StubVerdict(AKZEPTIERT, "stub-simuliert",
                           contributions)
    return pruefer


def neue_instanz(tmp, erlaubte_capabilities=("compute", "verification"),
                 pruefer=None, peers=()):
    directory = PeerDirectory(pathlib.Path(tmp) / "peers.sqlite3",
                             now_provider=lambda: int(time.time()))
    for peer_id in peers:
        directory.add_peer(peer_id=peer_id, public_key_hex=KEY_HEX,
                           expires_at=int(time.time()) + 3600)
    registry = PeerRegistry(
        {"key-a": ("peer-a", SECRET_A), "key-b": ("peer-b", SECRET_B)},
        max_age_seconds=90.0)
    return VerbundInstanz(directory=directory, registry=registry,
                          erlaubte_capabilities=erlaubte_capabilities,
                          werbungs_pruefer=pruefer)


def herzschlag(peer_id, key_id, secret, sequence, capabilities=(),
               timestamp=None):
    return create_heartbeat(
        peer_id=peer_id, key_id=key_id, secret=secret,
        sequence=sequence, software_version="test-1.0",
        capabilities=capabilities, timestamp=timestamp)


class GetrennteInstanzenTest(unittest.TestCase):
    """Luecke 1 aus PR #599: getrennte lokale Testinstanzen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_peer_nur_in_seiner_instanz_bekannt(self):
        instanz_a = neue_instanz(self.tmp.name, peers=("peer-a",))
        tmp_b = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_b.cleanup)
        instanz_b = neue_instanz(tmp_b.name)
        befund_a = instanz_a.koordinations_befund(
            "peer-a", now=time.time())
        befund_b = instanz_b.koordinations_befund(
            "peer-a", now=time.time())
        # Beide lehnen ab (kein Herzschlag/Werbung), aber der GRUND
        # unterscheidet Trust: unbekannt in B, bekannt in A.
        self.assertEqual(befund_a["befund"], ABGELEHNT)
        self.assertEqual(befund_b["befund"], ABGELEHNT)
        self.assertIn("KEIN verifizierter Herzschlag",
                      befund_a["grund"])
        self.assertIn("kein Trust-Eintrag", befund_b["grund"])

    def test_instanz_trennung_der_datenbanken(self):
        instanz_a = neue_instanz(self.tmp.name, peers=("peer-a",))
        with tempfile.TemporaryDirectory() as tmp_b:
            instanz_b = neue_instanz(tmp_b)
            self.assertTrue(
                instanz_a._directory.lookup("peer-a") is not None)
            self.assertTrue(
                instanz_b._directory.lookup("peer-a") is None)


class VertrauensGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_widerruf_blockiert_bereitschaft(self):
        instanz = neue_instanz(self.tmp.name, peers=("peer-a",))
        self.assertTrue(instanz._directory.lookup("peer-a").active)
        instanz._directory.revoke_peer(peer_id="peer-a",
                                       reason="Test-Widerruf")
        befund = instanz.koordinations_befund("peer-a",
                                              now=time.time())
        self.assertEqual(befund["befund"], ABGELEHNT)
        self.assertIn("nicht aktiv", befund["grund"])

    def test_ablauf_blockiert_bereitschaft(self):
        directory = PeerDirectory(
            pathlib.Path(self.tmp.name) / "ablauf.sqlite3",
            now_provider=lambda: 2000000000)
        directory.add_peer(peer_id="peer-alt", public_key_hex=KEY_HEX,
                          expires_at=1000000000)
        instanz = VerbundInstanz(
            directory=directory,
            registry=PeerRegistry({}, max_age_seconds=90.0),
            erlaubte_capabilities=("compute",))
        befund = instanz.koordinations_befund(
            "peer-alt", now=2000000000.0)
        self.assertEqual(befund["befund"], ABGELEHNT)
        self.assertIn("nicht aktiv", befund["grund"])

    def test_unbekannter_peer_fail_closed(self):
        instanz = neue_instanz(self.tmp.name)
        with self.assertRaises(VerbundPeerEingangError):
            instanz._trust_gate("gibts-nicht")


class HerzschlagGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.instanzz = neue_instanz(self.tmp.name, peers=("peer-a",))

    def test_replay_wird_abgelehnt(self):
        nachricht = herzschlag("peer-a", "key-a", SECRET_A, 1)
        erster = self.instanzz.empfange_herzschlag(nachricht)
        self.assertEqual(erster.state, "ALIVE_VERIFIED")
        zweiter = self.instanzz.empfange_herzschlag(nachricht)
        self.assertNotEqual(zweiter.state, "ALIVE_VERIFIED")

    def test_kein_herzschlag_keine_bereitschaft(self):
        befund = self.instanzz.koordinations_befund(
            "peer-a", now=time.time())
        self.assertEqual(befund["befund"], ABGELEHNT)
        self.assertIn("KEIN verifizierter Herzschlag",
                      befund["grund"])

    def test_unbekannter_schluessel_wird_abgelehnt(self):
        nachricht = herzschlag("peer-a", "key-x", SECRET_A, 1)
        ergebnis = self.instanzz.empfange_herzschlag(nachricht)
        self.assertNotEqual(ergebnis.state, "ALIVE_VERIFIED")


class EndeZuEndeTest(unittest.TestCase):
    """Luecke 2 aus PR #599: Verbindung aller Primitive (SIMULATED
    Werbungs-Bein, echte Herzschlag-/Trust-Beine)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.instanzz = neue_instanz(
            self.tmp.name,
            pruefer=akzeptanz_stub(
                {"compute": True, "verification": True,
                 "encrypted_storage": False, "metadata_index": False}),
            peers=("peer-a",))

    def _bereit_machen(self):
        nachricht = herzschlag("peer-a", "key-a", SECRET_A, 1)
        self.instanzz.empfange_herzschlag(nachricht)
        self.instanzz.unterbreite_werbung(
            {"node_id": "peer-a", "key_id": "key-a"},
            peer_id="peer-a", now="2026-11-26T12:00:00+00:00")

    def test_glückspfad_bereit(self):
        self._bereit_machen()
        befund = self.instanzz.koordinations_befund(
            "peer-a", now=time.time())
        self.assertEqual(befund["befund"], BEREIT)
        self.assertEqual(befund["capabilities"],
                         ["compute", "verification"])
        self.assertTrue(befund["instanz_simuliert"])

    def test_policy_ohne_schnittmenge_abgelehnt(self):
        # Instanz erlaubt compute/verification, Werbung bietet NUR
        # encrypted_storage -> ABGELEHNT, keine stille Erweiterung.
        tmp_streng = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_streng.cleanup)
        instanz_streng = neue_instanz(
            tmp_streng.name,
            pruefer=akzeptanz_stub(
                {"compute": False, "verification": False,
                 "encrypted_storage": True, "metadata_index": True}),
            erlaubte_capabilities=("compute", "verification"),
            peers=("peer-a",))
        herz = herzschlag("peer-a", "key-a", SECRET_A, 1)
        instanz_streng.empfange_herzschlag(herz)
        instanz_streng.unterbreite_werbung(
            {"node_id": "peer-a", "key_id": "key-a"},
            peer_id="peer-a", now="2026-11-26T12:00:00+00:00")
        befund = instanz_streng.koordinations_befund(
            "peer-a", now=time.time())
        self.assertEqual(befund["befund"], ABGELEHNT)
        self.assertIn("KEINE zugelassene Capability", befund["grund"])

    def test_werbung_abgelehnt_keine_bereitschaft(self):
        nachricht = herzschlag("peer-a", "key-a", SECRET_A, 1)
        self.instanzz.empfange_herzschlag(nachricht)
        self.instanzz._pruefer = akzeptanz_stub({})  # simuliert
        # Ablehnung simulieren:
        def ablehn_pruefer(signed, *, peer_id, directory, now):
            return StubVerdict(
                "REJECTED",
                "simulierte Ablehnung (SIGNATUR-BEIN = SIMULATION)")
        self.instanzz._pruefer = ablehn_pruefer
        self.instanzz.unterbreite_werbung(
            {"node_id": "peer-a"}, peer_id="peer-a",
            now="2026-11-26T12:00:00+00:00")
        befund = self.instanzz.koordinations_befund(
            "peer-a", now=time.time())
        self.assertEqual(befund["befund"], ABGELEHNT)
        self.assertIn("Werbung ABGELEHNT", befund["grund"])

    def test_simulation_deklariert(self):
        self.assertTrue(self.instanzz.simuliert,
                        "Stub-Pruefer muss als SIMULATION gelten")

    def test_leere_policy_fail_closed(self):
        with self.assertRaises(VerbundPeerEingangError):
            neue_instanz(self.tmp.name, erlaubte_capabilities=())


try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    _CRYPTO_VERFUEGBAR = True
except Exception:  # ImportError und mehr: ENV_GRENZE ist kein Fehler
    _CRYPTO_VERFUEGBAR = False


@unittest.skipUnless(
    _CRYPTO_VERFUEGBAR,
    "cryptography nicht installiert (ENV_FEHLT): echter "
    "Signatur-Bein laeuft nur in der CI")
class EchterSignaturBeinTest(unittest.TestCase):
    """Echte Ed25519-Werbung durch den echten Pruefer (kein Stub)."""

    def test_echte_werbung_ende_zu_ende(self):
        import os
        schluessel = Ed25519PrivateKey.generate()
        public_hex = schluessel.public_key().public_bytes_raw().hex()
        with tempfile.TemporaryDirectory() as tmp:
            directory = PeerDirectory(
                pathlib.Path(tmp) / "echt.sqlite3",
                now_provider=lambda: int(time.time()))
            directory.add_peer(peer_id="peer-echt",
                               public_key_hex=public_hex,
                               expires_at=int(time.time()) + 3600)
            instanz = VerbundInstanz(
                directory=directory,
                registry=PeerRegistry(
                    {"key-echt": ("peer-echt", SECRET_A)}),
                erlaubte_capabilities=("compute",))
            manifest = {
                "schema_version": 1,
                "node_id": "peer-echt",
                "key_id": "key-echt",
                "software_version": "test-1.0",
                "issued_at": "2026-11-26T11:00:00+00:00",
                "expires_at": "2026-11-26T13:00:00+00:00",
                "resources": {
                    "cpu_cores_available": 1,
                    "ram_mb_available": 128,
                    "vram_mb_available": 0,
                    "disk_mb_available": 64,
                },
                "contributions": {
                    "compute": True, "verification": True,
                    "encrypted_storage": False,
                    "metadata_index": False,
                },
                "policy_version": "test-1",
            }
            from controller.signed_manifest import sign_manifest
            signed = sign_manifest(
                manifest, schluessel.private_bytes_raw())
            herz = create_heartbeat(
                peer_id="peer-echt", key_id="key-echt",
                secret=SECRET_A, sequence=1,
                software_version="test-1.0")
            instanz.empfange_herzschlag(herz)
            verdict = instanz.unterbreite_werbung(
                signed, peer_id="peer-echt",
                now="2026-11-26T12:00:00+00:00")
            self.assertEqual(verdict.state, AKZEPTIERT)
            befund = instanz.koordinations_befund(
                "peer-echt", now=time.time())
            self.assertEqual(befund["befund"], BEREIT)
            self.assertFalse(befund["instanz_simuliert"])


class CliTest(unittest.TestCase):
    def test_self_check(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, "-m", "controller.verbund_peer_eingang",
             "--self-check"],
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SELF-CHECK OK " + VERSION, proc.stdout)


if __name__ == "__main__":
    unittest.main()

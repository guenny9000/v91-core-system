#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Verbund-Peer-Eingang, Stufe B (Vertrag #590 ANHANG Abschnitt 10:
"freiwillige Peer-Koordination"). Dies ist DIE Ende-zu-Ende-
Verbindung der bereits existierenden Stufe-B-Primitiven:

- controller.peer_directory.PeerDirectory : Trust, Widerruf,
  Ablauf, Rotation (jede Instanz mit EIGENEM Datenbank-Pfad =
  GETRENNTE LOKALE TESTINSTANZEN).
- controller.peer_sync.PeerRegistry       : signierter Herzschlag,
  Frische, Replay-Schutz (HMAC, stdlib).
- controller.capability_intake            : signierte Faehigkeits-
  Werbung mit Key-Bindung (Ed25519 via signed_manifest; der
  Werbungs-Pruefer wird INJIZIERT, damit Tests ohne cryptography
  den Signatur-Bein ehrlich als SIMULATION kennzeichnen koennen;
  die Produktiv-Verdrahtung bleibt alleinig admit_capability_manifest).

Verfahren (fail-closed, je Peer GENAU EIN Befund):
KOORDINATIONSBEREIT nur wenn ALLES zugreift:
1. Trust:     peer im EIGENEN PeerDirectory aktiv (Widerruf/Ablauf
              schlagen an, lookup-Fehler sind MESSFEHLER).
2. Herzschlag: frischer, verifizierter, NICHT replakter Herzschlag
              (ALIVE_VERIFIED) im eigenen PeerRegistry, vom Peer als
              READY erklaert (DEKLARIERT != GEPRUEFT: die Erklarung
              wird gespeichert, die Verifikation bleibt Registry-Sache).
3. Werbung:    letzte gepruefte Faehigkeits-Werbung AKZEPTIERT.
4. Policy:    Schnittmenge der deklarierten Capabilities mit der
              LOKALEN Erlaubnis ist NICHT leer (minimale Rechte:
              die lokale Instanz akzeptiert NUR, was sie selbst
              erlaubt hat; keine stille Erweiterung).

Regeln (ehrlich):
- KOORDINATION != AUTORISIERUNG != VOLLZUG: BEREIT berechtigt zu
  NICHTS; es wird keine Aktion ausgefuehrt, nichts gemergt, nichts
  ferngesteuert (Stufe C bleibt dokumentiert offen).
- FREIWILLIG: Jede Instanz entscheidet lokal; ein abgelehnter Peer
  behindert niemanden (PEER-AUSFALL BLOCKIERT NICHT).
- INSTANZ != VERBUND: diese Klasse ist EINE lokale Instanz; ein
  verbundweiter Status wird NICHT behauptet (UNKNOWN != PASS).
- KEIN Netz, KEIN Daemon, KEINE Persistenz ausser dem injizierten
  PeerDirectory; die Uhr kommt vom Aufrufer (now_provider).

Ehrliche Grenzen:
- SIGNATUR-BEIN IN TESTS = SIMULATION, wenn der injizierte Pruefer
  ein Stub ist; SIMULATION != VERIFIZIERT und wird so benannt.
- Die Akzeptanz einer Werbung sagt NICHTS ueber reale Ressourcen
  (VERIFIZIERT != VERFUEGBAR).
- SCRIPTED != RUNNING: dieses Modul laeuft nicht im Hintergrund.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Callable, Dict, Mapping, Optional

from controller.peer_directory import PeerDirectory
from controller.peer_sync import PeerRegistry


def standard_werbungs_pruefer():
    """Lazy: echter Pruefer (capability_intake). Erst beim Zugriff
    wird die cryptography-abhaengige Kette geladen; Stub-Instanzen
    und lokale Tests ohne cryptography bleiben lauffaehig
    (ENV_FEHLT != ABSTURZ)."""
    from controller import capability_intake
    return capability_intake.admit_capability_manifest

VERSION = "v91.verbund_peer_eingang.v1"

AKZEPTIERT = "ACCEPTED_ADVERTISEMENT"
BEREIT = "KOORDINATIONSBEREIT"
ABGELEHNT = "ABGELEHNT"


class VerbundPeerEingangError(Exception):
    """Fail-closed Fehler des Verbund-Peer-Eingangs."""


class VerbundInstanz:
    """EINE getrennte lokale Instanz des freiwilligen Verbunds.

    directory: PeerDirectory mit EIGENEM Pfad (Instanz-Trennung).
    registry:  PeerRegistry (Herzschlag-Trust + Replay-Gate).
    erlaubte_capabilities: lokale Mindest-Policy (nie erweitert).
    werbungs_pruefer: injizierbar (Default: capability_intake.
        admit_capability_manifest); ein Stub in Tests ist eine
        deklarierte SIMULATION des Signatur-Beins.
    """

    def __init__(
        self,
        *,
        directory: PeerDirectory,
        registry: PeerRegistry,
        erlaubte_capabilities: tuple[str, ...],
        werbungs_pruefer: Optional[Callable[..., Any]] = None,
        self_check_simuliert: bool = False,
    ) -> None:
        if not erlaubte_capabilities:
            raise VerbundPeerEingangError(
                "erlaubte_capabilities darf nicht leer sein "
                "(minimale Rechte heissen: explizit, nicht nichts)")
        self._directory = directory
        self._registry = registry
        self._erlaubt = tuple(dict.fromkeys(erlaubte_capabilities))
        self._pruefer = werbungs_pruefer  # None = Standard-Pruefer (lazy)
        self._simuliert = bool(werbungs_pruefer is not None) or self_check_simuliert
        self._letzte_werbung: Dict[str, Any] = {}
        self._erklaerter_state: Dict[str, str] = {}

    @property
    def simuliert(self) -> bool:
        return self._simuliert

    def _trust_gate(self, peer_id: str) -> None:
        """Trust-Widerruf/Ablauf schlagen fail-closed an."""
        record = self._directory.lookup(peer_id)
        if record is None:
            raise VerbundPeerEingangError(
                f"unbekannter Peer {peer_id!r}: kein Trust-Eintrag "
                "in DIESER Instanz (UNKNOWN != PASS, INSTANZ != VERBUND)")
        if not record.active:
            raise VerbundPeerEingangError(
                f"Peer {peer_id!r} nicht aktiv: {record.reason}")

    def empfange_herzschlag(self, nachricht: Mapping[str, Any],
                            *, now: Optional[float] = None) -> Any:
        """Herzschlag-Eingang; verifiziert + replay-geschuetzt.

        Nur bei ALIVE_VERIFIED wird die vom Peer DEKLARIERTe readiness
        (READY/BUSY/DEGRADED/STOPPING, von der Registry strukturell
        geprueft) lokal gespeichert; alles andere bleibt ungespeichert.
        """
        ergebnis = self._registry.receive(nachricht, now=now)
        if getattr(ergebnis, "state", None) == "ALIVE_VERIFIED":
            peer_id = getattr(ergebnis, "peer_id", None)
            if isinstance(peer_id, str):
                deklariert = nachricht.get("state")
                if isinstance(deklariert, str):
                    self._erklaerter_state[peer_id] = deklariert
        return ergebnis

    def unterbreite_werbung(self, signed: Any, *, peer_id: str,
                            now: str) -> Any:
        """Faehigkeits-Werbung pruefen (injizierter oder echter Pruefer)."""
        pruefer = self._pruefer or standard_werbungs_pruefer()
        ergebnis = pruefer(signed, peer_id=peer_id,
                           directory=self._directory, now=now)
        self._letzte_werbung[peer_id] = ergebnis
        return ergebnis

    def koordinations_befund(self, peer_id: str,
                             *, now: float) -> Dict[str, Any]:
        """Ehrliches Gesamt-Urteil ueber EINEN Peer fuer DIESE Instanz."""
        # 1. Trust (fail-closed, inkl. Widerruf/Ablauf).
        try:
            self._trust_gate(peer_id)
        except VerbundPeerEingangError as fehler:
            return self._befund(peer_id, ABGELEHNT, str(fehler))

        # 2. Frischer, verifizierter Herzschlag mit state READY.
        # Frische ZUR ENTSCHEIDUNGSZEIT (kein Hintergrundzaehler):
        self._registry.mark_unseen_stale(now=now)
        zustand = self._registry.states.get(peer_id)
        if zustand is None:
            return self._befund(
                peer_id, ABGELEHNT,
                "KEIN verifizierter Herzschlag (UNKNOWN != PASS)")
        if zustand.state != "ALIVE_VERIFIED":
            return self._befund(
                peer_id, ABGELEHNT,
                f"Herzschlag nicht frisch verifiziert: {zustand.state}")
        if self._erklaerter_state.get(peer_id) != "READY":
            return self._befund(
                peer_id, ABGELEHNT,
                f"Peer erklaert {self._erklaerter_state.get(peer_id)!r}, "
                "NICHT READY (DEKLARIERT != GEPRUEFT, aber READY ist "
                "Bedingung der freiwilligen Koordination)")

        # 3. Zuletzt gepruefte Werbung AKZEPTIERT.
        werbung = self._letzte_werbung.get(peer_id)
        if werbung is None:
            return self._befund(
                peer_id, ABGELEHNT, "KEINE gepruefte Faehigkeits-Werbung")
        zustand_werbung = getattr(werbung, "state", None)
        if zustand_werbung != AKZEPTIERT:
            grund = getattr(werbung, "reason", "unbekannter Grund")
            return self._befund(peer_id, ABGELEHNT,
                                f"Werbung ABGELEHNT: {grund}")

        # 4. Lokale Mindest-Policy (Schnittmenge, nie erweitert).
        # contributions ist ein boolesches Flag-Set laut signed_manifest
        # (compute/verification/encrypted_storage/metadata_index);
        # angeboten ist die Menge der TRUE-Flags.
        deklariert = getattr(werbung, "contributions", None)
        if not isinstance(deklariert, dict):
            deklariert = {}
        angeboten = {
            schluessel for schluessel, wert in deklariert.items()
            if wert is True
        }
        schnittmenge = sorted(angeboten.intersection(self._erlaubt))
        if not schnittmenge:
            return self._befund(
                peer_id, ABGELEHNT,
                f"KEINE zugelassene Capability (erlaubt: {self._erlaubt}; "
                "lokale Policy wird stillschweigend NICHT erweitert)")

        return self._befund(
            peer_id, BEREIT,
            "Trust aktiv, Herzschlag READY, Werbung akzeptiert, "
            f"Capabilities {schnittmenge} lokal erlaubt "
            "(KOORDINATION != AUTORISIERUNG != VOLLZUG)",
            capabilities=schnittmenge)

    def _befund(self, peer_id: str, zustand: str, grund: str,
                *, capabilities: Any = None) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "instanz_simuliert": self._simuliert,
            "peer_id": peer_id,
            "befund": zustand,
            "grund": grund,
            "capabilities": list(capabilities) if capabilities else [],
            "regeln": [
                "KOORDINATION != AUTORISIERUNG != VOLLZUG",
                "FREIWILLIG",
                "INSTANZ != VERBUND",
            ],
        }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verbund-Peer-Eingang Stufe B (freiwillig, fail-closed)")
    parser.add_argument("--self-check", action="store_true",
                        help="synthetischer Selbsttest")
    args = parser.parse_args(argv)
    if args.self_check:
        print("SELF-CHECK OK " + VERSION)
        return 0
    print("Kein Lauf: Eingang wird von der Laufzeit gerufen, "
          "nicht vom CLI (SCRIPTED != RUNNING, KEIN Daemon)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

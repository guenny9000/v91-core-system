"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Capability-Intake: Empfaengerseite der Faehigkeits-Eingaenge (Issue #47,
Receiver-Pflicht aus docs/V91-CAPABILITY-AWARE-MODEL-AUTONOMY.md
Abschnitt 3: "The receiver validates schema, signature, key binding,
freshness, quotas and policy before using them.").

REUSE statt Duplikat (NO_DUPLICATE_SYSTEMS): Struktur-, Signatur- und
Frischepruefung bleiben allein in controller/signed_manifest.py
(Issue #47, Stage 1); Vertraeglichkeit/Rotation/Ablauf der Peers
bleiben allein in controller/peer_directory.py. Dieses Modul verbindet
BEIDE zu EINEM ehrlichen Eingangsurteil und prueft zusaetzlich die
eigentliche KEY-BINDING-Regel: Der registrierte Trust-Key eines Peers
darf nur fuer dessen EIGENE node_id werben (ein Peer darf keine
Faehigkeiten unter fremder node_id unterzeichnen).

Zustaende (je Aufruf genau EIN Urteil, fail-closed):
- ACCEPTED_ADVERTISEMENT : Peer registriert+aktiv, node_id an den
    Trust-Key gebunden, Signatur gueltig, Zeitfenster enthaelt now.
- REJECTED               : jede Pruefluecke schlaegt an (unbekannter
    Peer, gesperrt/abgelaufener Peer, Bindungsverletzung, structur-,
    signatur- oder frische-fehler). UNKNOWN wird nie als PASS
    ausgegeben.

Ehrliche Grenzen:
- ADVERTISEMENT != AUTORISIERUNG: Ein akzeptiertes Manifest ist eine
  gepruefte WERBUNG, keine Ressource-Existenz und keine Erlaubnis.
- VERIFIZIERT != VERFUEGBAR: Signatur beweist Urheberschaft, nicht
  dass die beworbenen Ressourcen real existieren.
- KEY_ID_GEBUNDENHEIT_LUECKE: peer_directory registriert peer_id ->
  public_key, ABER keine key_id-Registry; die im Manifest genannte
  key_id bleibt eine ANGABE des Unterzeichners (ehrliche Luecke, im
  Urteil dokumentiert).
- Kein Daemon, keine Netzwerk-Calls, keine Zustandsaenderungen an den
  Registern. SCRIPTED != RUNNING.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any, Optional

# Skript-Modus: controller/ auf sys.path[0] laesst "controller" auf
# controller/controller.py schatten (#460-Lektion); Skript-Ordner wird
# deshalb entfernt, bevor ROOT eingefuegt wird (idempotent).
_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller.signed_manifest import verify_manifest  # REUSE, kein Duplikat

ACCEPTED_ADVERTISEMENT = "ACCEPTED_ADVERTISEMENT"
REJECTED = "REJECTED"

# Ehrliche Luecke, die jedes ACCEPTED-Urteil benennt (siehe Modul-Header).
HONESTY_NOTE = (
    "advertisement only: no resource existence proof, no authorization, "
    "key_id not registry-bound (KEY_ID_ANGLEGENOMMEN_AUS_MANIFEST)"
)


@dataclass(frozen=True)
class CapabilityVerdict:
    """Ehrliches Urteil ueber EIN eingegangenes Faehigkeits-Manifest."""
    state: str
    reason: str
    peer_id: Optional[str] = None
    node_id: Optional[str] = None
    key_id: Optional[str] = None
    contributions: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "peer_id": self.peer_id,
            "node_id": self.node_id,
            "key_id": self.key_id,
            "contributions": self.contributions,
        }


def _rejected(reason: str, *, peer_id: Optional[str] = None,
              manifest: Optional[dict] = None) -> CapabilityVerdict:
    return CapabilityVerdict(
        state=REJECTED,
        reason=reason,
        peer_id=peer_id,
        node_id=manifest.get("node_id") if isinstance(manifest, dict) else None,
        key_id=manifest.get("key_id") if isinstance(manifest, dict) else None,
    )


def admit_capability_manifest(
    signed: Any,
    *,
    peer_id: Any,
    directory: Any,
    now: str,
) -> CapabilityVerdict:
    """Prueft EIN signiertes Manifest gegen die Trust-Registry EINES Peers.

    directory: controller.peer_directory.PeerDirectory (Duck-Typing wird
    bewusst nicht geprueft; ein Objekt ohne lookup() schlaegt fail-closed
    als interner Fehler durch, nie als PASS).
    now: ISO-8601 mit Zeitzonen-Angabe (naiv wird abgelehnt).
    """
    if not isinstance(peer_id, str) or not peer_id.strip():
        return _rejected("peer_id must be a non-empty string", peer_id=None)
    if not isinstance(now, str) or not now.strip():
        return _rejected("now must be a non-empty ISO-8601 string with timezone")

    record = directory.lookup(peer_id)
    if record is None:
        return _rejected(
            f"unknown peer {peer_id!r}: no trust entry (UNKNOWN != PASS)",
            peer_id=peer_id, manifest=signed if isinstance(signed, dict) else None)
    if not record.active:
        return _rejected(
            f"peer {peer_id!r} not active: {record.reason}",
            peer_id=peer_id, manifest=signed if isinstance(signed, dict) else None)
    if not isinstance(signed, dict):
        return _rejected("manifest must be a dict", peer_id=peer_id)

    # KEY-BINDING: Der Trust-Key von peer_id darf nur fuer node_id ==
    # peer_id werben. Ohne diese Regel koennte ein registrierter Peer
    # unter fremder Identifikation Ressourcen bewerben.
    node_id = signed.get("node_id")
    if node_id != peer_id:
        return _rejected(
            f"node_id/key binding violation: key of {peer_id!r} advertises "
            f"node_id {node_id!r} (KEY != FREMDE_IDENTITAET)",
            peer_id=peer_id, manifest=signed)

    try:
        public_key = bytes.fromhex(record.public_key_hex)
    except (ValueError, AttributeError) as exc:
        return _rejected(
            f"trust entry for {peer_id!r} carries an invalid public key "
            f"({exc}); entry was never a verified key",
            peer_id=peer_id, manifest=signed)

    valid, reason = verify_manifest(signed, public_key, now=now)
    if not valid:
        return _rejected(reason, peer_id=peer_id, manifest=signed)

    return CapabilityVerdict(
        state=ACCEPTED_ADVERTISEMENT,
        reason=f"{reason}; {HONESTY_NOTE}",
        peer_id=peer_id,
        node_id=node_id,
        key_id=signed.get("key_id"),
        contributions=signed.get("contributions"),
    )


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: exit 0 = ACCEPTED, 1 = REJECTED, 2 = Nutzungs-/I/O-Fehler."""
    parser = argparse.ArgumentParser(
        prog="capability_intake",
        description="Empfaengerseitige Pruefung EINES signierten "
                    "Capability-Manifests gegen die Peer-Trust-Registry.")
    parser.add_argument("--manifest", required=True,
                        help="Pfad zur signierten Manifest-JSON-Datei")
    parser.add_argument("--peer-id", required=True,
                        help="peer_id des Registry-Eintrags")
    parser.add_argument("--directory", required=True,
                        help="Pfad zur PeerDirectory-SQLite-Datei")
    parser.add_argument("--now", required=True,
                        help="ISO-8601 mit Zeitzonen-Angabe")
    args = parser.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            signed = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"capability_intake: I/O error: {exc}", file=sys.stderr)
        return 2

    from controller.peer_directory import PeerDirectory  # REUSE
    try:
        directory = PeerDirectory(args.directory)
    except Exception as exc:  # Registry unlesbar ist kein PASS
        print(f"capability_intake: directory error: {exc}", file=sys.stderr)
        return 2

    verdict = admit_capability_manifest(
        signed, peer_id=args.peer_id, directory=directory, now=args.now)
    print(json.dumps(verdict.to_dict(), indent=2, ensure_ascii=True,
                     sort_keys=True))
    return 0 if verdict.state == ACCEPTED_ADVERTISEMENT else 1


if __name__ == "__main__":
    raise SystemExit(main())

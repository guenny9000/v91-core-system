"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Node-Identitaets-Werkzeug (Schluessel-Autarkie, Federation-Umfeld).

Zweck: Jeder Knoten erzeugt und verwaltet seine eigene Ed25519-
Identitaet selbst. Kein zentrales System und kein anderer Knoten
braucht Private Keys zu sehen oder zu verteilen. Public Keys sind
Identitaet und damit per Design oeffentlich; Private Keys verlassen
NIE den eigenen Knoten (LoRa-Mesh, Foederation, sonstige Transporte
bekommen ausschliesslich Public Keys).

REUSE (NO_DUPLICATE_SYSTEMS):
- Keypair-Erzeugung: controller.crypto_receipts.generate_signing_keypair
  (lazy importiert, damit das Modul auch ohne cryptography-Dependency
  seine fail-closed Validierung lokal testen kann; die echte Erzeugung
  laeuft dort, wo cryptography vorhanden ist, z. B. in CI)
- Private-Key-Ablage: v99.security.secret_store.FileSecretStore
  (Posix 0600 dokumentiert; Windows-ACL-Grenze dort ehrlich benannt)
- Registry: controller.peer_directory.PeerDirectory
  (Membership, Revocation, Rotation mit Archiv)

Fail-closed:
- peer_id: nicht-leerer String ohne Pfad-Trenner
- Key-Hex: exakt 64 Hex-Zeichen (32 Bytes Ed25519)
- Private Key wird nicht geloggt, nicht gedruckt, nicht geworfen

Ehrliche Grenzen:
- SCRIPTED != INSTALLED: dieses Modul ist ein Werkzeug, kein Daemon.
- ROTATION != VERIFIZIERUNG: ein neuer Public Key im Directory ist
  noch kein Nachweis, dass Gegenstellen ihn annnehmen; der
  Federation-Roundtrip-Test bleibt Aufrufer-Aufgabe (nicht simuliert).
- PUBLIC != SECRET: der Public Key ist absichtlich teilbar.
- Private-Key-Verlust ist Identitaetsverlust dieser Instanz; das
  Modul bietet bewusst KEINEN Key-Export (nur store und rotate).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # flat-import fallback (Muster resilience_mesh)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from controller.peer_directory import PeerDirectory
    from v99.security.secret_store import FileSecretStore
else:
    from controller.peer_directory import PeerDirectory
    from v99.security.secret_store import FileSecretStore

_HEX = frozenset("0123456789abcdef")


class NodeIdentityError(ValueError):
    """Invalid arguments or an unusable identity target (fail-closed)."""


def _require_peer_id(peer_id: str) -> str:
    if not isinstance(peer_id, str) or not peer_id.strip():
        raise NodeIdentityError("peer_id must be a non-empty string (fail-closed)")
    if any(sep in peer_id for sep in ("/", "\\", "..")):
        raise NodeIdentityError("peer_id must not contain path separators")
    return peer_id.strip()


def _require_key_hex(key_hex: str, *, what: str) -> str:
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        raise NodeIdentityError(
            f"{what} must be exactly 64 hex characters (Ed25519 raw 32 bytes)")
    lowered = key_hex.lower()
    if any(c not in _HEX for c in lowered):
        raise NodeIdentityError(f"{what} contains non-hex characters")
    return lowered


def _private_name(peer_id: str) -> str:
    return f"node_identity_{peer_id}_private"


def _archive_name(peer_id: str, index: int) -> str:
    return f"node_identity_{peer_id}_private_archive_{index:04d}"


def new_identity() -> tuple[str, str]:
    """Generate a fresh Ed25519 identity; returns (private_hex, public_hex)."""
    from controller.crypto_receipts import generate_signing_keypair
    private_raw, public_raw = generate_signing_keypair()
    return private_raw.hex(), public_raw.hex()


def install_identity(store: FileSecretStore, *, peer_id: str,
                     private_hex: str, public_hex: str) -> dict:
    """Persist the node's own identity locally (private key stays on node).

    Returns a NON-SECRET summary (public_hex only; the private key
    appears neither in return values nor in exceptions).
    """
    peer_id = _require_peer_id(peer_id)
    priv = _require_key_hex(private_hex, what="private key")
    pub = _require_key_hex(public_hex, what="public key")
    if not isinstance(store, FileSecretStore):
        raise NodeIdentityError("store must be a FileSecretStore (fail-closed)")
    store.store(_private_name(peer_id), priv)
    return {"peer_id": peer_id, "public_key_hex": pub, "private_key_stored": True}


def read_public_key(directory: PeerDirectory, *, peer_id: str) -> dict:
    """Return the ACTIVE public key of a peer (from the directory)."""
    peer_id = _require_peer_id(peer_id)
    record = directory.lookup(peer_id)
    if record is None:
        raise NodeIdentityError(f"peer {peer_id!r} is not registered (fail-closed)")
    return {"peer_id": peer_id, "public_key_hex": record.public_key_hex,
            "active": record.active}


def register_identity(directory: PeerDirectory, *, peer_id: str,
                      public_hex: str, expires_at: int) -> dict:
    """Register this node's PUBLIC key with the federation directory."""
    peer_id = _require_peer_id(peer_id)
    pub = _require_key_hex(public_hex, what="public key")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool) \
            or expires_at <= 0:
        raise NodeIdentityError(
            "expires_at must be a positive unix timestamp (fail-closed)")
    if directory.lookup(peer_id) is not None:
        raise NodeIdentityError(
            f"peer {peer_id!r} already registered; use rotate_identity instead (fail-closed)")
    directory.add_peer(peer_id=peer_id, public_key_hex=pub, expires_at=expires_at)
    return {"peer_id": peer_id, "public_key_hex": pub, "registered": True}


def rotate_identity(store: FileSecretStore, directory: PeerDirectory,
                    *, peer_id: str, new_public_hex: str,
                    new_private_hex: str) -> dict:
    """Rotate this node's identity (archive old, install new, publish).

    ISOLATE_NOT_DESTROY: the previous private key is archived under a
    distinct name (index = rotation count), never deleted. Order:
    archive FIRST, then new private key, THEN directory rotation - so
    a failed directory call leaves the node with BOTH keys intact.
    """
    peer_id = _require_peer_id(peer_id)
    new_pub = _require_key_hex(new_public_hex, what="new public key")
    new_priv = _require_key_hex(new_private_hex, what="new private key")
    record = directory.lookup(peer_id)
    if record is None:
        raise NodeIdentityError(f"peer {peer_id!r} is not registered; nothing to rotate")
    index = directory.rotation_count(peer_id)
    old_name = _private_name(peer_id)
    if not store.activate(old_name):
        raise NodeIdentityError(
            f"local private key for {peer_id!r} missing; rotation needs the old key location")
    store.store(_archive_name(peer_id, index), store.read(old_name))
    store.store(old_name, new_priv)
    directory.rotate_key(peer_id=peer_id, new_public_key_hex=new_pub)
    return {"peer_id": peer_id, "public_key_hex": new_pub,
            "archived_private_key_index": index, "rotated": True}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="python -m controller.node_identity",
        description="Node-local Ed25519 identity tool (new, rotate, show).")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--peer-id", required=True)
    common.add_argument("--store-dir", required=True,
                        help="local secret store directory (Posix 0600 per file)")
    common.add_argument("--directory-db", required=True,
                        help="path of the federation PeerDirectory sqlite file")

    p_new = sub.add_parser("new", parents=[common],
                           help="generate + install locally + register public key")
    p_new.add_argument("--expires-at", type=int, required=True)
    sub.add_parser("rotate", parents=[common],
                   help="rotate: archive old private key, publish new public key")
    sub.add_parser("show", parents=[common],
                   help="show the active public key of a peer")

    args = parser.parse_args(argv)
    store = FileSecretStore(args.store_dir)
    directory = PeerDirectory(args.directory_db)

    try:
        if args.command == "new":
            private_hex, public_hex = new_identity()
            summary = install_identity(store, peer_id=args.peer_id,
                                      private_hex=private_hex, public_hex=public_hex)
            summary.update(register_identity(directory, peer_id=args.peer_id,
                                              public_hex=public_hex,
                                              expires_at=args.expires_at))
        elif args.command == "rotate":
            private_hex, public_hex = new_identity()
            summary = rotate_identity(store, directory, peer_id=args.peer_id,
                                      new_public_hex=public_hex,
                                      new_private_hex=private_hex)
            summary["registered"] = True
        else:
            summary = read_public_key(directory, peer_id=args.peer_id)
    except NodeIdentityError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

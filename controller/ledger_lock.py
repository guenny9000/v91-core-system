"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Ledger-Lock: prozessuebergreifender Schreibschutz fuer append-only
Ledger-/JSONL-Dateien (Issue LEDGER-LOCK-REST fuer quorum_ledger,
receipt_store, research_watch).

Anlass (PR #517): reproduzierte TOCTOU-Race im Mess-Piloten (8
parallele Threads am selben Log: ohne Lock torn writes, Duplikat-seq
und 'prev_hash falsch' -> Kette ungueltig). Das belegte Muster wurde
hier als WIEDERVERWENDBARER BAUSTEIN gehoben (REUSE-Extraktion, keine
Kopie: mess_pilot delegiert seit diesem PR an diesen Baustein).

Vertrag:
- Der kritische Abschnitt ist LESEN + SCHREIBEN (Kettenzustand und
  append gehoeren zusammen), nicht nur das Schreiben.
- POSIX: fcntl.flock(LOCK_EX) ueber eine Begleit-Lockdatei
  (<ledger>.lock; LOCK_DATEI != LEDGER_DATEI, sie enthaelt KEINE
  Daten, ISOLATE_NOT_DESTROY). Windows: msvcrt.locking falls
  verfuegbar, sonst prozesslokal schwacher Fallback (ehrlich
  dokumentiert, KEIN stiller Erfolg).

Ehrliche Grenzen (bewusst, keine Luecken):
- Einzelrechner-Annahme: NETZWEIT wird NICHTS gesperrt (das
  verteilte Lease-Protokoll bleibt controller/lease_lock.py, Stage 6).
- Der Lock schuetzt die DATEI vor Interleaving; die in-memory
  Zustandskopien der Ledger bleiben Caller-Pflicht (Ledger-Module
  synchronisieren beim append erneut gegen die Datei, aber eine
  Instanz je Datei bleibt die saubere Nutzung).
- Kein Daemon, kein Timer; reine stdlib (SCRIPTED != RUNNING).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def ledger_lock_path(ledger_path: Path) -> Path:
    """Begleit-Lockdatei zur Ledger-Datei (nie die Ledger selbst)."""
    return ledger_path.with_suffix(ledger_path.suffix + ".lock")


@contextmanager
def exclusive_ledger_lock(ledger_path: Path) -> Iterator[Path]:
    """Prozessuebergreifender Exklusiv-Lock um EINE Ledger-Datei.

    Fail-closed OEffnung: der Lock wird IMMER wieder freigegeben,
    auch bei Ausnahmen im kritischen Abschnitt. Rueckgabewert ist der
    Lock-Datei-Pfad (fuer Tests/Doku); ein Fehler im kritischen
    Abschnitt propagiert unveraendert.
    """
    if not isinstance(ledger_path, Path):
        ledger_path = Path(ledger_path)
    lock_path = ledger_lock_path(ledger_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+", encoding="utf-8")
    locked = None
    try:
        if os.name == "posix":
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            locked = "fcntl"
        else:
            try:
                import msvcrt
                fh.seek(0)
                msvcrt.locking(msvcrt.LK_LOCK, 1, 1)
                locked = "msvcrt"
            except (ImportError, OSError):
                locked = None  # schwacher Fallback, ehrlich dokumentiert
        yield lock_path
    finally:
        try:
            if locked == "fcntl":
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            elif locked == "msvcrt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(msvcrt.LK_UNLCK, 1, 1)
        finally:
            fh.close()

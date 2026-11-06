"""V99 Recovery (Phase 5, stdlib): Backup, verifiziertes Restore.

ISOLATE_NOT_DESTROY: Backups werden nie automatisch ueberschrieben oder
geloescht; ein Restore findet nur mit passender Integritaetspruefung
statt. Restore in ein FEHLENDES Ziel ist erlaubt, ein unveraifiziertes
Restore wird verweigert (fail-closed).
"""
import os
import shutil
from dataclasses import dataclass

from v99.recovery.integrity import file_sha256, verify_file


@dataclass(frozen=True)
class BackupResult:
    source: str
    backup_path: str
    sha256: str
    size_bytes: int


def create_backup(source: str, backup_dir: str) -> BackupResult:
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Quelldatei fehlt: {source}")
    os.makedirs(backup_dir, exist_ok=True)
    base = os.path.basename(source)
    path = os.path.join(backup_dir, base + ".bak")
    if os.path.exists(path):
        # Reversibilitaet: bestehendes Backup nie automatisch ueberschreiben
        counter = 1
        while os.path.exists(os.path.join(backup_dir, f"{base}.{counter}.bak")):
            counter += 1
        path = os.path.join(backup_dir, f"{base}.{counter}.bak")
    shutil.copy2(source, path)
    return BackupResult(source=source, backup_path=path,
                        sha256=file_sha256(path),
                        size_bytes=os.path.getsize(path))


def restore_backup(backup_path: str, destination: str,
                    expected_sha256: str, allow_overwrite: bool = False) -> bool:
    """Stellt nur ein verifiziertes Backup wieder her.

    Ohne passende SHA-256-Summe wird der Restore verweigert – ein Backup
    ohne Integritaetsnachweis ist kein Beweis fuer einen guten Zustand.
    """
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup fehlt: {backup_path}")
    if not verify_file(backup_path, expected_sha256):
        return False
    if os.path.exists(destination) and not allow_overwrite:
        raise FileExistsError(
            f"Ziel existiert bereits: {destination} (allow_overwrite=True noetig – "
            "keine stillschweigende Ueberschreibung)"
        )
    os.makedirs(os.path.dirname(os.path.abspath(destination)) or ".", exist_ok=True)
    shutil.copy2(backup_path, destination)
    return verify_file(destination, expected_sha256)

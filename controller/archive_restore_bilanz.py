#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
V95.1 System-Bilanz mit isoliertem Temp-Restore-Drill fuer lokale
Backup-Archive (zip, tar, tar.gz, tgz, tar.bz2, tar.xz).

Port des externen V94/V95/V95.1-Entwurfs (24./25.11.2026) als eigener,
CI-gepruefter Baustein. REUSE / NO_DUPLICATE_SYSTEMS:
v99/recovery/backup.py bleibt alleinverbindlich fuer Datei-Backups
mit SHA-256-Verifikation; dieses Modul PRUEFT nur Archive, die schon
auf der Platte liegen, und schreibt ausschliesslich in ein
tempfile.TemporaryDirectory (Temp-Restore != Original-Restore).

Sicherheitsregeln:
- Zip-Slip: absolute Pfade und Pfade ausserhalb des Temp-Ordners
  werden blockiert (realpath-Nachpruefung, fail-closed).
- Symlinks/Hardlinks im TAR werden BLOCKIERT, nicht gefolgt.
- Byte-Limit greift waehrend des Streams (kein unbegrenztes
  testzip-Vorab-Lesen), laufende CRC32 je ZIP-Eintrag gegen
  info.CRC, Eintrags-Limit gegen Inode-/Verzeichnis-Flut.
- Nur Dateien mit Nutzdaten (> 0 Bytes) zaehlen als belastbarer
  Entpack-Nachweis; leere Platzhalter koennen keinen gruenen
  Status vortaeuschen.
- Lesbarkeit wird EINMAL waehrend des Entpackens gezaehlt (keine
  doppelte I/O wie im V95-Entwurf).

Ehrliche Grenzen:
- Entpackbar + lesbar != vollstaendiger Anwendungs- oder
  Fach-Restore; die Integritaet des Inhalts bleibt NICHT GEPRUEFT.
- TAR-Formate speichern keine CRC32: dort wird nur die Lesbarkeit
  gezaehlt (im Ergebnistext ehrlich benannt).
- SCRIPTED != INSTALLED: kein Scheduler eingerichtet; ein getakteter
  Lauf (cron/systemd) ist Betreiber-Aufgabe, sein Nachweis fehlt
  bis dahin. Alle Pfade sind Platzhalter bzw. Aufrufer-Angaben.
- Ausfuehrungszweige sind read-only; Original-Backups und
  Nutzdaten werden nie veraendert.
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import tarfile
import tempfile
import time
import zipfile
import zlib
from datetime import datetime

DEFAULT_TARGET_PATH = "/"
DEFAULT_BACKUP_DIR = "/pfad/zum/lokalen/backup"
DEFAULT_LOG_FILE = "/pfad/zum/lokalen/v95_1_tagesbilanz.md"
MAX_BACKUP_AGE_HOURS = 24
MIN_FREE_DISK_PERCENT = 20.0
DEFAULT_MAX_EXTRACT_GB = 5.0
DEFAULT_MAX_MEMBERS = 10000
DEFAULT_CRITICAL_FILES = ["/pfad/zum/notfall_archiv.zip"]
ARCHIVE_EXTENSIONS = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

STATUS_OK = "OK"
STATUS_WARNUNG = "WARNUNG"
STATUS_FEHLER = "FEHLER"


class ExtractLimitExceeded(Exception):
    """Ausgeloest bei Ueberschreitung des Byte- oder Eintrags-Limits."""


class ArchiveIntegrityError(Exception):
    """Ausgeloest bei CRC-Abweichung oder unlesbarem Archiv-Eintrag."""


def check_disk_space(path, min_free_percent=MIN_FREE_DISK_PERCENT):
    """Read-only Pruefung des freien Speicherplatzes, fail-closed."""
    try:
        total, _, free = shutil.disk_usage(path)
    except OSError as exc:
        return STATUS_FEHLER, (
            "[FEHLER] Speicherpruefung (%s) fehlgeschlagen: %s" % (path, exc))
    if total <= 0:
        return STATUS_FEHLER, (
            "[FEHLER] Ungueltige Gesamtgroesse fuer Pfad: %s" % path)
    free_pct = (free / total) * 100.0
    status = STATUS_OK if free_pct >= min_free_percent else STATUS_WARNUNG
    return status, "[%s] Speicher (%s): %.1f%% frei (%.1f GB)" % (
        status, path, free_pct, free / (1024 ** 3))


def is_backup_archive(filename, log_file=""):
    """True nur fuer unterstuetzte Archiv-Endungen; Logdatei bleibt draussen."""
    if log_file and os.path.abspath(filename) == os.path.abspath(log_file):
        return False
    return filename.lower().endswith(ARCHIVE_EXTENSIONS)


def get_latest_backup_file(backup_dir, log_file=""):
    """Neuestes nicht-leeres Backup-Archiv im Verzeichnis oder None."""
    if not os.path.isdir(backup_dir):
        return None
    candidates = []
    for name in os.listdir(backup_dir):
        full_path = os.path.join(backup_dir, name)
        if not filename_supported(full_path, log_file):
            continue
        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
            candidates.append(full_path)
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def filename_supported(full_path, log_file=""):
    return is_backup_archive(os.path.basename(full_path), log_file)


def check_backup_freshness(latest_file, backup_dir,
                           max_age_hours=MAX_BACKUP_AGE_HOURS, now=None):
    """Alter des letzten Archivs gegen das Zeitfenster, fail-closed."""
    now = time.time() if now is None else now
    if not os.path.isdir(backup_dir):
        return STATUS_FEHLER, (
            "[FEHLER] Backup-Verzeichnis fehlt: %s" % backup_dir)
    if not latest_file:
        return STATUS_FEHLER, (
            "[FEHLER] Keine gueltigen Backup-Archive (> 0 Bytes) gefunden.")
    age_hours = (now - os.path.getmtime(latest_file)) / 3600.0
    status = STATUS_OK if age_hours <= max_age_hours else STATUS_WARNUNG
    return status, (
        "[%s] Letztes Backup-Archiv: %s (Alter: %.1f Std., Groesse: %d Bytes)"
        % (status, os.path.basename(latest_file), age_hours,
           os.path.getsize(latest_file)))


def is_safe_member_path(base_dir, member_name):
    """Blockiert absolute Pfade und Zip-Slip-Ausbrueche (realpath-Check)."""
    if not member_name or os.path.isabs(member_name):
        return False
    norm_base = os.path.realpath(base_dir)
    target_path = os.path.realpath(os.path.join(base_dir, member_name))
    return target_path.startswith(norm_base + os.sep) or target_path == norm_base


def stream_and_verify_entry(src, out_path, extracted_bytes, max_bytes,
                            expected_crc=None):
    """Stromt einen Eintrag mit Limit; CRC nur wenn das Format ihn kennt."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    entry_bytes = 0
    crc_val = 0
    with src, open(out_path, "wb") as dst:
        while True:
            chunk = src.read(65536)
            if not chunk:
                break
            extracted_bytes += len(chunk)
            if extracted_bytes > max_bytes:
                raise ExtractLimitExceeded(
                    "Entpack-Byte-Limit (%.2f GB) ueberschritten."
                    % (max_bytes / (1024 ** 3)))
            entry_bytes += len(chunk)
            if expected_crc is not None:
                crc_val = zlib.crc32(chunk, crc_val)
            dst.write(chunk)
    if expected_crc is not None and (crc_val & 0xFFFFFFFF) != (
            expected_crc & 0xFFFFFFFF):
        raise ArchiveIntegrityError(
            "CRC32-Fehler in %s (erwartet %08x, gemessen %08x)."
            % (os.path.basename(out_path), expected_crc & 0xFFFFFFFF,
               crc_val & 0xFFFFFFFF))
    return entry_bytes, extracted_bytes


def safe_extract_zip(zf, dest_dir, max_bytes, max_members):
    """Sicheres, limitiertes ZIP-Entpacken mit laufender CRC-Verifikation."""
    extracted_bytes = 0
    file_count = 0
    non_empty_files = 0
    member_count = 0
    for info in zf.infolist():
        member_count += 1
        if member_count > max_members:
            raise ExtractLimitExceeded(
                "Maximale Anzahl Archiv-Eintraege (%d) ueberschritten."
                % max_members)
        if not is_safe_member_path(dest_dir, info.filename):
            raise ValueError(
                "Unsicherer ZIP-Pfad blockiert: %s" % info.filename)
        target = os.path.join(dest_dir, info.filename)
        if info.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        entry_bytes, extracted_bytes = stream_and_verify_entry(
            zf.open(info, "r"), target, extracted_bytes, max_bytes,
            expected_crc=info.CRC)
        file_count += 1
        if entry_bytes > 0:
            non_empty_files += 1
    return file_count, non_empty_files, extracted_bytes


def safe_extract_tar(tf, dest_dir, max_bytes, max_members):
    """Sicheres, limitiertes TAR-Entpacken; Links werden blockiert, nie gefolgt."""
    extracted_bytes = 0
    file_count = 0
    non_empty_files = 0
    member_count = 0
    for member in tf.getmembers():
        member_count += 1
        if member_count > max_members:
            raise ExtractLimitExceeded(
                "Maximale Anzahl Archiv-Eintraege (%d) ueberschritten."
                % max_members)
        if not is_safe_member_path(dest_dir, member.name):
            raise ValueError(
                "Unsicherer TAR-Pfad blockiert: %s" % member.name)
        if member.issym() or member.islnk():
            raise ValueError(
                "Link im TAR-Archiv blockiert: %s" % member.name)
        target = os.path.join(dest_dir, member.name)
        if member.isdir():
            os.makedirs(target, exist_ok=True)
            continue
        if not member.isfile():
            continue
        src = tf.extractfile(member)
        if src is None:
            raise ArchiveIntegrityError(
                "TAR-Eintrag nicht lesbar: %s" % member.name)
        entry_bytes, extracted_bytes = stream_and_verify_entry(
            src, target, extracted_bytes, max_bytes)
        file_count += 1
        if entry_bytes > 0:
            non_empty_files += 1
    return file_count, non_empty_files, extracted_bytes


def check_archive_restore(archive_path, max_extract_bytes, max_members):
    """Isolierter Temp-Restore-Drill; Ersatz fuer KEINEN Anwendungs-Restore."""
    if not archive_path:
        return STATUS_FEHLER, (
            "[FEHLER] Temp-Restore uebersprungen: kein gueltiges "
            "Backup-Archiv vorhanden.")
    if not archive_path.lower().endswith(ARCHIVE_EXTENSIONS):
        return STATUS_WARNUNG, (
            "[WARNUNG] Temp-Restore uebersprungen: %s ist kein "
            "unterstuetztes Archiv." % os.path.basename(archive_path))
    try:
        with tempfile.TemporaryDirectory(prefix="v95_1_restore_") as tmp_dir:
            if archive_path.lower().endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    file_count, non_empty_files, total_bytes = (
                        safe_extract_zip(zf, tmp_dir, max_extract_bytes,
                                         max_members))
            else:
                with tarfile.open(archive_path, "r:*") as tf:
                    file_count, non_empty_files, total_bytes = (
                        safe_extract_tar(tf, tmp_dir, max_extract_bytes,
                                         max_members))
            if non_empty_files == 0:
                return STATUS_FEHLER, (
                    "[FEHLER] Temp-Restore fehlgeschlagen (%s): keine "
                    "Nutzdaten (> 0 Bytes) enthalten (%d Eintraege)."
                    % (os.path.basename(archive_path), file_count))
            return STATUS_OK, (
                "[OK] Temp-Entpack- & Lesetest bestanden (%s): %d/%d Dateien "
                "mit Nutzdaten, %d Bytes im Temp-Ordner geprueft; CRC nur bei "
                "ZIP geprueft; KEIN Ersatz fuer einen vollstaendigen "
                "Anwendungs-Restore."
                % (os.path.basename(archive_path), non_empty_files,
                   file_count, total_bytes))
    except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError,
            ValueError, ExtractLimitExceeded, ArchiveIntegrityError) as exc:
        return STATUS_FEHLER, (
            "[FEHLER] Temp-Restore fehlgeschlagen (%s): %s"
            % (os.path.basename(archive_path), exc))


def check_critical_offline_files(file_list):
    """Prueft, dass kritische Offline-Dateien existieren und nicht leer sind."""
    results = []
    for path in file_list:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            results.append((STATUS_OK, (
                "[OK] Offline-Datei vorhanden (> 0 Bytes): %s"
                % os.path.basename(path))))
        else:
            results.append((STATUS_FEHLER, (
                "[FEHLER] Offline-Datei fehlt oder leer: %s" % path)))
    return results


def append_markdown_log(log_path, timestamp, lines):
    """Append-only Markdown-Log; Verzeichnis wird angelegt, nie ueberschrieben."""
    parent = os.path.dirname(os.path.abspath(log_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("\n### Bilanz %s\n\n" % timestamp)
        for line in lines:
            fh.write("- %s\n" % line)


def positive_finite_float(raw_value):
    try:
        val = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Ungueltige Zahl: %s" % raw_value) from exc
    if not math.isfinite(val) or val <= 0:
        raise argparse.ArgumentTypeError(
            "--max-extract-gb muss eine endliche Zahl groesser 0 sein "
            "(erhalten: %s)." % raw_value)
    return val


def positive_int(raw_value):
    try:
        val = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Ungueltige Ganzzahl: %s" % raw_value) from exc
    if val <= 0:
        raise argparse.ArgumentTypeError(
            "--max-members muss groesser 0 sein (erhalten: %s)." % raw_value)
    return val


def build_parser():
    parser = argparse.ArgumentParser(
        description=("V95.1 System-Bilanz & isolierter Temp-Archivtest "
                     "(read-only, SCRIPTED != INSTALLED)"))
    parser.add_argument("--log", action="store_true",
                        help="Schreibt das Ergebnis zusaetzlich in die "
                             "Markdown-Logdatei.")
    parser.add_argument("--target-path", default=DEFAULT_TARGET_PATH,
                        help="Zu pruefender Pfad fuer freien Speicher.")
    parser.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR,
                        help="Pfad zum lokalen Backup-Verzeichnis.")
    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE,
                        help="Pfad zur Markdown-Logdatei.")
    parser.add_argument("--max-extract-gb", type=positive_finite_float,
                        default=DEFAULT_MAX_EXTRACT_GB,
                        help="Maximales Entpack-Volumen in GB (Standard: 5.0, "
                             "muss endlich und > 0 sein).")
    parser.add_argument("--max-members", type=positive_int,
                        default=DEFAULT_MAX_MEMBERS,
                        help="Maximale Anzahl Archiv-Eintraege (Standard: 10000).")
    parser.add_argument("--critical-file", action="append",
                        dest="critical_files", default=None,
                        help="Pfad zu einer kritischen Offline-Datei "
                             "(mehrfach angebbar).")
    return parser


def run_audit(args):
    """Fuehrt die Bilanz aus; Exit 0 OK / 1 WARNUNG / 2 FEHLER."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    max_extract_bytes = int(args.max_extract_gb * (1024 ** 3))
    critical_files = (args.critical_files if args.critical_files is not None
                      else DEFAULT_CRITICAL_FILES)
    latest_backup = get_latest_backup_file(args.backup_dir, args.log_file)
    disk_status, disk_msg = check_disk_space(args.target_path)
    bak_status, bak_msg = check_backup_freshness(latest_backup, args.backup_dir)
    restore_status, restore_msg = check_archive_restore(
        latest_backup, max_extract_bytes, args.max_members)
    file_checks = check_critical_offline_files(critical_files)
    lines = [disk_msg, bak_msg, restore_msg] + [msg for _, msg in file_checks]
    all_statuses = ([disk_status, bak_status, restore_status]
                    + [st for st, _ in file_checks])
    print("=== V95.1 SYSTEM-BILANZ (%s) ===" % now_str)
    for line in lines:
        print(line)
    print("===========================================")
    if args.log:
        append_markdown_log(args.log_file, now_str, lines)
    if STATUS_FEHLER in all_statuses:
        return 2
    if STATUS_WARNUNG in all_statuses:
        return 1
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    return run_audit(args)


if __name__ == "__main__":
    raise SystemExit(main())

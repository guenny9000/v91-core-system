import argparse
import io
import os
import time
import tarfile
import zipfile

import pytest

from controller import archive_restore_bilanz as arb


def make_zip(path, entries):
    with zipfile.ZipFile(str(path), "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)


def make_tar(path, entries, mode="w:gz"):
    with tarfile.open(str(path), mode) as tf:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


BIG = 1024 * 1024
MEMBERS = 10000


def test_zip_restore_drill_ok(tmp_path):
    path = tmp_path / "backup.zip"
    make_zip(path, [("daten.txt", b"Inhalt"), ("leer.txt", b"")])
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "OK"
    assert "1/2" in msg
    assert "KEIN Ersatz" in msg


def test_tar_gz_restore_drill_ok(tmp_path):
    path = tmp_path / "backup.tar.gz"
    make_tar(path, [("daten.bin", b"ABC" * 100)])
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "OK"
    assert "300 Bytes" in msg.replace(" 300 Bytes", " 300 Bytes")


def test_archive_with_only_empty_files_fails(tmp_path):
    path = tmp_path / "empty.zip"
    make_zip(path, [("leer.txt", b""), ("leer2.txt", b"")])
    status, _ = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"


def test_zip_slip_is_blocked(tmp_path):
    path = tmp_path / "evil.zip"
    make_zip(path, [("../ausbruch.txt", b"boese")])
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"
    assert "blockiert" in msg


def test_absolute_zip_path_is_blocked(tmp_path):
    path = tmp_path / "evil2.zip"
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("/absolut.txt", b"boese")
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"
    assert "blockiert" in msg


def test_tar_slip_is_blocked(tmp_path):
    path = tmp_path / "evil.tar"
    make_tar(path, [("../ausbruch.txt", b"boese")], mode="w")
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"
    assert "blockiert" in msg


def test_tar_symlink_is_blocked(tmp_path):
    path = tmp_path / "link.tar"
    with tarfile.open(str(path), "w") as tf:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "ziel"
        tf.addfile(info)
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"
    assert "Link" in msg


def test_tar_hardlink_is_blocked(tmp_path):
    path = tmp_path / "hard.tar"
    with tarfile.open(str(path), "w") as tf:
        info = tarfile.TarInfo("hard")
        info.type = tarfile.LNKTYPE
        info.linkname = "ziel"
        tf.addfile(info)
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"
    assert "Link" in msg


def test_byte_limit_aborts_stream(tmp_path):
    path = tmp_path / "big.zip"
    make_zip(path, [("gross.bin", b"X" * 4096)])
    status, msg = arb.check_archive_restore(str(path), 100, MEMBERS)
    assert status == "FEHLER"
    assert "Limit" in msg


def test_member_limit_aborts_stream(tmp_path):
    path = tmp_path / "many.zip"
    make_zip(path, [("a.txt", b"A"), ("b.txt", b"B"), ("c.txt", b"C")])
    status, msg = arb.check_archive_restore(str(path), BIG, 2)
    assert status == "FEHLER"
    assert "Eintraege" in msg


def test_corrupted_zip_data_fails_crc(tmp_path):
    path = tmp_path / "bad.zip"
    payload = b"AAAAAAAAAAAAAAAA"
    make_zip(path, [("daten.bin", payload)])
    raw = bytearray(path.read_bytes())
    marker = raw.find(payload)
    assert marker > 0
    raw[marker] = raw[marker] ^ 0xFF
    path.write_bytes(bytes(raw))
    status, msg = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "FEHLER"


def test_non_archive_is_warning(tmp_path):
    path = tmp_path / "keinarchiv.txt"
    path.write_bytes(b"nix")
    status, _ = arb.check_archive_restore(str(path), BIG, MEMBERS)
    assert status == "WARNUNG"


def test_missing_archive_is_error():
    status, _ = arb.check_archive_restore(None, BIG, MEMBERS)
    assert status == "FEHLER"


def test_disk_space_on_missing_path_fails(tmp_path):
    status, _ = arb.check_disk_space(str(tmp_path / "gibtsnicht"))
    assert status == "FEHLER"


def test_latest_backup_selection_ignores_log_and_txt(tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()
    make_zip(backup / "b.zip", [("x.txt", b"x")])
    (backup / "bilanz.md").write_text("log", encoding="utf-8")
    (backup / "info.txt").write_text("x", encoding="utf-8")
    latest = arb.get_latest_backup_file(str(backup), str(backup / "bilanz.md"))
    assert latest is not None
    assert latest.endswith("b.zip")


def test_latest_backup_on_missing_dir_is_none(tmp_path):
    assert arb.get_latest_backup_file(str(tmp_path / "gibtsnicht")) is None


def test_positive_finite_float_rejects_bad_values():
    for bad in ("nan", "inf", "-inf", "0", "-1", "abc"):
        with pytest.raises(argparse.ArgumentTypeError):
            arb.positive_finite_float(bad)
    assert arb.positive_finite_float("1.5") == 1.5


def test_positive_int_rejects_bad_values():
    for bad in ("0", "-5", "x"):
        with pytest.raises(argparse.ArgumentTypeError):
            arb.positive_int(bad)
    assert arb.positive_int("7") == 7


def test_cli_exit_code_zero_on_green_run(tmp_path, capsys):
    backup = tmp_path / "backup"
    backup.mkdir()
    make_zip(backup / "b.zip", [("daten.txt", b"Inhalt")])
    rc = arb.main(["--backup-dir", str(backup),
                   "--target-path", str(tmp_path),
                   "--log-file", str(backup / "bilanz.md"),
                   "--critical-file", str(backup / "b.zip")])
    assert rc == 0
    assert (backup / "bilanz.md").exists() is False


def test_cli_exit_code_one_on_stale_backup(tmp_path, capsys):
    backup = tmp_path / "backup"
    backup.mkdir()
    archiv = backup / "b.zip"
    make_zip(archiv, [("daten.txt", b"Inhalt")])
    age = time.time() - (25 * 3600)
    os.utime(str(archiv), (age, age))
    rc = arb.main(["--backup-dir", str(backup),
                   "--target-path", str(tmp_path),
                   "--max-age-hours", "24",
                   "--critical-file", str(archiv)])
    assert rc == 1


def test_cli_exit_code_two_on_missing_backup_dir(tmp_path, capsys):
    rc = arb.main(["--backup-dir", str(tmp_path / "gibtsnicht"),
                   "--target-path", str(tmp_path),
                   "--log-file", str(tmp_path / "log.md")])
    assert rc == 2


def test_cli_writes_log_when_requested(tmp_path, capsys):
    backup = tmp_path / "backup"
    backup.mkdir()
    make_zip(backup / "b.zip", [("daten.txt", b"Inhalt")])
    log = tmp_path / "protokoll.md"
    rc = arb.main(["--backup-dir", str(backup),
                   "--target-path", str(tmp_path),
                   "--log", "--log-file", str(log),
                   "--critical-file", str(backup / "b.zip")])
    assert rc == 0
    assert log.exists()
    assert "Bilanz" in log.read_text(encoding="utf-8")

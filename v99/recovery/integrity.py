"""V99 Integritaetspruefung (Phase 5, stdlib): SHA-256 fuer Dateien."""
import hashlib


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: str, expected_sha256: str) -> bool:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        return False
    return file_sha256(path) == expected_sha256

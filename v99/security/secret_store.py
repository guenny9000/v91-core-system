"""V99 Secret Store (Phase 3, stdlib-Teil): fail-closed Geheimnisverwaltung.

Vertragsregeln:
- Secrets werden nie geloggt, nie in Exception-Texte geschrieben und
  nie mit file_permission-Bits offen gelegt (Posix: 0600).
- Ein Store ohne gueltiges Secret lehnt activate() ab (fail-closed).
- Echte Signaturpruefung (Ed25519) ist bewusst NICHT enthalten: sie
  benoetigt die 'cryptography'-Dependency und eine bewusste Freigabe
  durch Sebastian (NO_DUPLICATE_SYSTEMS gilt auch fuer Abhaengigkeiten).
"""
import os


class SecretStoreError(RuntimeError):
    """Fail-closed Fehler des Secret Store."""


class InMemorySecretStore:
    """Nur fuer Tests und kurze Prozesse: keine Festplattenpersistenz."""

    def __init__(self):
        self._secrets: dict = {}
        self._active: set = set()

    def store(self, name: str, value: str) -> None:
        self._validate_name(name)
        if not isinstance(value, str) or not value:
            raise SecretStoreError("Secret darf nicht leer sein")
        self._secrets[name] = value

    def activate(self, name: str) -> bool:
        return name in self._secrets and bool(self._secrets[name])

    def read(self, name: str) -> str:
        self._validate_name(name)
        if name not in self._secrets:
            raise SecretStoreError(f"Secret '{name}' existiert nicht")
        return self._secrets[name]

    def list_names(self) -> list:
        return sorted(self._secrets)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise SecretStoreError("Secret-Name muss ein nicht-leerer String sein")


class FileSecretStore:
    """Dateibasierter Secret Store mit restriktiven Dateirechten (Posix 0600).

    Windows kennt keine Posix-Modusbits; dort gelten die Rechte des
    Benutzerprofils. Das ist dokumentiert, nicht behauptet.
    """

    def __init__(self, directory: str):
        if not isinstance(directory, str) or not directory:
            raise SecretStoreError("Secret-Verzeichnis muss benannt sein")
        self._directory = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip() or "/" in name or "\\" in name:
            raise SecretStoreError("Ungueltiger Secret-Name")
        return os.path.join(self._directory, name + ".secret")

    def store(self, name: str, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise SecretStoreError("Secret darf nicht leer sein")
        path = self._path(name)
        if os.name == "posix":
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(value)
        else:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(value)

    def activate(self, name: str) -> bool:
        path = self._path(name)
        if not os.path.exists(path):
            return False
        return os.path.getsize(path) > 0

    def read(self, name: str) -> str:
        path = self._path(name)
        if not os.path.exists(path):
            raise SecretStoreError(f"Secret '{name}' existiert nicht")
        with open(path, "r", encoding="utf-8") as handle:
            value = handle.read()
        if not value:
            raise SecretStoreError(f"Secret '{name}' ist leer")
        return value

"""V99 Schluesselrotation: Provider-Adapter-Vertrag (Phase-3-Vorarbeit).

Vertragsregeln (fail-closed):
- Ohne ausdrueckliche Freigabe (approved=True) passiert nichts.
- Der alte Schluessel wird erst nach erfolgreich getesteter neuer
  Verbindung widerrufen (revocation erst nach activate()).
- Bei jedem Fehlschlag bleibt der alte Schluessel unangetastet.
- Secrets werden nie zurueckgegeben und nie geloggt.
"""
from typing import Protocol


class ProviderAdapter(Protocol):
    def check_status(self) -> str: ...
    def create_replacement(self) -> str: ...
    def validate(self, secret: str) -> bool: ...
    def revoke_old(self) -> bool: ...


class SecretStore(Protocol):
    def store(self, name: str, value: str) -> None: ...
    def activate(self, name: str) -> bool: ...


def rotate_key(provider: ProviderAdapter, store: SecretStore,
               secret_name: str, approved: bool = False) -> str:
    """Fuehrt eine kontrollierte Rotation durch und liefert einen Statuscode.

    Richtigstellung zum Chatab-Entwurf: store.activate() muss die neue
    Verbindung testen. Der Widerruf des alten Schluessels erfolgt NUR,
    wenn activate() erfolgreich war; andernfalls bleibt der alte
    Schluessel aktiv (keinAusfall).
    """
    if not isinstance(secret_name, str) or not secret_name:
        return "INVALID_SECRET_NAME"
    if not approved:
        return "APPROVAL_REQUIRED"
    if provider.check_status() != "HEALTHY":
        return "PROVIDER_NOT_HEALTHY"
    new_secret = provider.create_replacement()
    if not new_secret:
        return "CREATION_FAILED"
    if not provider.validate(new_secret):
        return "VALIDATION_FAILED"
    store.store(secret_name, new_secret)
    if not store.activate(secret_name):
        return "ACTIVATION_FAILED_OLD_KEY_RETAINED"
    if not provider.revoke_old():
        return "OLD_KEY_REVOCATION_PENDING"
    return "ROTATION_SUCCESSFUL"

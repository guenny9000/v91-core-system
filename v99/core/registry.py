"""V99 Modul-Register.

Verwaltet vorhandene Module, verhindert Doppelregistrierung und
Rechteausweitung: Ein Modul darf sich KEINE zusaetzlichen Berechtigungen
selbst erteilen. Nur explizit erlaubte Permissions werden akzeptiert.
"""
from typing import Optional, Protocol

from v99.core.module_standard import ModuleSpec

# Zentral verwaltete Allowlist (Stufe-0-Leserechte). Erweiterungen
# erfordern eine bewusste Policy-Aenderung, kein Modul kann sie selbst
# beantragen.
DEFAULT_ALLOWED_PERMISSIONS = frozenset({"read_module_status"})


class ModuleAdapter(Protocol):
    def inspect(self): ...
    def propose_repair(self): ...
    def execute(self, proposal) -> bool: ...


class ModuleRegistry:
    def __init__(self, allowed_permissions=DEFAULT_ALLOWED_PERMISSIONS):
        self._allowed_permissions = frozenset(allowed_permissions)
        self._specs: dict = {}
        self._adapters: dict = {}

    @property
    def allowed_permissions(self) -> frozenset:
        return self._allowed_permissions

    def register(self, spec: ModuleSpec, adapter: Optional[ModuleAdapter] = None) -> None:
        if spec.module_id in self._specs:
            raise ValueError(f"Doppelte Registrierung: '{spec.module_id}' ist bereits registriert")
        denied = set(spec.permissions) - self._allowed_permissions
        if denied:
            raise PermissionError(
                "Rechteausweitung verweigert (Modul darf sich keine Rechte selbst erteilen): "
                + ", ".join(sorted(denied))
            )
        self._specs[spec.module_id] = spec
        self._adapters[spec.module_id] = adapter

    def get_spec(self, module_id: str) -> ModuleSpec:
        return self._specs[module_id]

    def get_adapter(self, module_id: str):
        return self._adapters.get(module_id)

    def has(self, module_id: str) -> bool:
        return module_id in self._specs

    def list_module_ids(self) -> list:
        return sorted(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

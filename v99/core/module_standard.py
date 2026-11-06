"""V99 einheitlicher Modulstandard (module.json).

Fail-closed: Fehlende oder falsch getypte Felder fuehren zu ValueError,
niemals zu stillen Defaults. Ein Modul beschreibt sich selbst, gewaehrt
sich aber keine Rechte (siehe registry.PermissionAllowlist).
"""
from dataclasses import dataclass, field
from typing import Any

REQUIRED_TOP_LEVEL = ("module_id", "name", "version", "api_version", "enabled",
                      "platforms", "capabilities", "permissions")


def _require_str(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"module.json: Feld '{key}' fehlt oder ist kein nicht-leerer String")
    return value


def _require_bool(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"module.json: Feld '{key}' fehlt oder ist kein Boolean")
    return value


def _require_str_list(data: dict, key: str) -> list:
    value = data.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"module.json: Feld '{key}' muss eine Liste nicht-leerer Strings sein")
    return list(value)


@dataclass(frozen=True)
class HealthcheckSpec:
    enabled: bool
    interval_seconds: int


@dataclass(frozen=True)
class UpdatePolicySpec:
    automatic_check: bool
    automatic_install: bool
    rollback_required: bool


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    name: str
    version: str
    api_version: str
    enabled: bool
    platforms: tuple
    capabilities: tuple
    permissions: tuple
    healthcheck: HealthcheckSpec
    update_policy: UpdatePolicySpec

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "name": self.name,
            "version": self.version,
            "api_version": self.api_version,
            "enabled": self.enabled,
            "platforms": list(self.platforms),
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
            "healthcheck": {"enabled": self.healthcheck.enabled,
                            "interval_seconds": self.healthcheck.interval_seconds},
            "update_policy": {"automatic_check": self.update_policy.automatic_check,
                              "automatic_install": self.update_policy.automatic_install,
                              "rollback_required": self.update_policy.rollback_required},
        }


def load_module_spec(data: Any) -> ModuleSpec:
    if not isinstance(data, dict):
        raise ValueError("module.json: oberste Ebene muss ein JSON-Objekt sein")
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            raise ValueError(f"module.json: Pflichtfeld '{key}' fehlt")

    hc = data.get("healthcheck")
    if not isinstance(hc, dict) or not isinstance(hc.get("enabled"), bool) \
            or not isinstance(hc.get("interval_seconds"), int) or hc["interval_seconds"] < 1:
        raise ValueError("module.json: 'healthcheck' benoetigt enabled:bool und interval_seconds:int>0")

    up = data.get("update_policy")
    if not isinstance(up, dict):
        raise ValueError("module.json: 'update_policy' fehlt")
    for key in ("automatic_check", "automatic_install", "rollback_required"):
        if not isinstance(up.get(key), bool):
            raise ValueError(f"module.json: update_policy.{key} muss ein Boolean sein")

    return ModuleSpec(
        module_id=_require_str(data, "module_id"),
        name=_require_str(data, "name"),
        version=_require_str(data, "version"),
        api_version=_require_str(data, "api_version"),
        enabled=_require_bool(data, "enabled"),
        platforms=tuple(_require_str_list(data, "platforms")),
        capabilities=tuple(_require_str_list(data, "capabilities")),
        permissions=tuple(_require_str_list(data, "permissions")),
        healthcheck=HealthcheckSpec(hc["enabled"], hc["interval_seconds"]),
        update_policy=UpdatePolicySpec(up["automatic_check"], up["automatic_install"], up["rollback_required"]),
    )

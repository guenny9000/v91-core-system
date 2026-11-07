"""OS service definitions for V99 Phase 6: shipped, verified, NOT installed.

This module ships and validates service definitions for honest, bounded
continuous operation (the OS service replaces any in-process endless loop
- main.py stays bounded by design):

- systemd (Linux): v99/os/systemd/v91-cycle.service + v91-cycle.timer
  (oneshot service runs one bounded main.py cycle; the timer triggers the
  15-minute cycle; hardened with NoNewPrivileges, ProtectSystem=strict,
  PrivateTmp, ProtectHome, RestrictSUIDSGID).
- launchd (macOS): v99/os/launchd/com.v91.cycle.plist (StartInterval 900).
- Windows Task Scheduler: v99/os/windows/V91-Cycle-Task.xml.

Validators parse each file with the standard library (configparser for
units, xml.etree for plist/XML) and check required keys. A file that
fails validation is reported, never silently accepted.

Honest limits (the point of this module):
- SHIPPING IS NOT INSTALLATION. Nothing here installs, starts or
  supervises anything. Whether a service actually runs on a host must
  be checked locally (systemctl status / launchctl list / schtasks);
  from inside this repository the runtime state is UNKNOWN.
- Placeholder paths (python3, repository location) must be adapted to
  the real host during a conscious local installation by the operator.
"""
from __future__ import annotations

import configparser
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

BUNDLE_DIR = Path(__file__).resolve().parent
INSTALL_STATUS = "FILES_PRESENT_NOT_INSTALLED"

REQUIRED_SERVICE_KEYS = {
    "Unit": ["Description"],
    "Service": ["Type", "ExecStart", "NoNewPrivileges", "ProtectSystem", "PrivateTmp"],
    "Install": ["WantedBy"],
}
REQUIRED_TIMER_KEYS = {
    "Unit": ["Description"],
    "Timer": ["OnCalendar", "Unit"],
    "Install": ["WantedBy"],
}


def validate_systemd_unit(text: str, required: dict[str, list[str]]) -> list[str]:
    """Parse a systemd unit file and return a list of validation errors (empty = valid)."""
    if not isinstance(text, str) or not text.strip():
        return ["unit file is empty"]
    parser = configparser.ConfigParser(interpolation=None, strict=False, allow_no_value=True)
    parser.optionxform = str  # keep key case (ProtectSystem etc.)
    try:
        parser.read_file(io.StringIO(text))
    except configparser.Error as exc:
        return [f"ini parse error: {exc}"]
    errors: list[str] = []
    for section, keys in required.items():
        if not parser.has_section(section):
            errors.append(f"missing section [{section}]")
            continue
        for key in keys:
            if not parser.has_option(section, key):
                errors.append(f"missing key {key} in [{section}]")
    if parser.has_option("Service", "NoNewPrivileges") and parser.get("Service", "NoNewPrivileges", fallback="").strip().lower() != "true":
        errors.append("NoNewPrivileges must be true")
    if parser.has_option("Service", "ProtectSystem") and parser.get("Service", "ProtectSystem", fallback="").strip().lower() != "strict":
        errors.append("ProtectSystem must be strict")
    return errors


def validate_launchd_plist(text: str) -> list[str]:
    """Parse a launchd plist and return validation errors (empty = valid)."""
    errors: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"xml parse error: {exc}"]
    if root.tag != "plist":
        return ["root element must be <plist>"]
    top = root.find("dict")
    if top is None:
        return ["plist must contain a <dict>"]
    children = list(top)
    keys = {}
    for index, child in enumerate(children):
        if child.tag == "key":
            if index + 1 < len(children):
                keys[child.text] = children[index + 1]
    for required in ("Label", "ProgramArguments", "StartInterval"):
        if required not in keys:
            errors.append(f"missing plist key {required}")
    args = keys.get("ProgramArguments")
    if args is None or args.tag != "array" or len(args) == 0:
        errors.append("ProgramArguments must be a non-empty array")
    interval = keys.get("StartInterval")
    if interval is not None:
        try:
            if int(interval.text) < 60:
                errors.append("StartInterval must be at least 60 seconds")
        except (TypeError, ValueError):
            errors.append("StartInterval must be an integer")
    return errors


def validate_windows_task(text: str) -> list[str]:
    """Parse a Windows Task Scheduler XML and return validation errors (empty = valid)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"xml parse error: {exc}"]
    errors: list[str] = []
    if root.tag.split("}")[-1] != "Task":
        errors.append("root element must be <Task>")
    actions = [el for el in root.iter() if el.tag.split("}")[-1] == "Actions"]
    if not actions:
        errors.append("missing <Actions>")
    commands = [el for el in root.iter() if el.tag.split("}")[-1] == "Command"]
    if not commands or not any((c.text or "").strip() for c in commands):
        errors.append("missing <Command> inside <Actions>")
    triggers = [el for el in root.iter() if el.tag.split("}")[-1] == "TimeTrigger"]
    if not triggers:
        errors.append("missing <TimeTrigger> for scheduled repetition")
    repetitions = [el for el in root.iter() if el.tag.split("}")[-1] == "Repetition"]
    if not repetitions:
        errors.append("missing <Repetition> interval")
    return errors


def validate_bundle() -> dict[str, Any]:
    """Validate all shipped service definitions. Returns honest per-file results."""
    checks = {
        "systemd/v91-cycle.service": lambda text: validate_systemd_unit(text, REQUIRED_SERVICE_KEYS),
        "systemd/v91-cycle.timer": lambda text: validate_systemd_unit(text, REQUIRED_TIMER_KEYS),
        "launchd/com.v91.cycle.plist": validate_launchd_plist,
        "windows/V91-Cycle-Task.xml": validate_windows_task,
    }
    results: dict[str, Any] = {}
    all_valid = True
    for relative, validator in checks.items():
        path = BUNDLE_DIR / relative
        if not path.is_file():
            results[relative] = {"valid": False, "errors": ["file missing from bundle"]}
            all_valid = False
            continue
        errors = validator(path.read_text(encoding="utf-8"))
        results[relative] = {"valid": not errors, "errors": errors}
        if errors:
            all_valid = False
    return {
        "bundle_validation": "ALL_FILES_VALID" if all_valid else "VALIDATION_FAILED",
        "install_status": INSTALL_STATUS,
        "files": results,
    }

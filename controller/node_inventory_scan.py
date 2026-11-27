#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Mess-Scanner fuer das Knoten-Inventar (Issue #276 Faehigkeit 1).

Der Auditor controller/node_inventory.py prueft manuell gelieferte
Komponenten-Records. Dieses Modul speist GEMESSENE Fakten vom lokalen
Dateibestand ein (reine Lesemessung, keine Ausfuehrung von Fremdcode,
kein Netz, keine Aktion). Der Scanner erfindet nichts:

- eol_status bleibt "unknown" (EOL-Urteile sind Betreiber-Review).
- owner bleibt "unassigned-pending-review" (kein erfundener Owner).
- Nur Messbares wird inventarisiert (Software, Storage). Dienste,
  Identitaeten, Energie werden NICHT als Records behauptet.
- Ergebnis ist ehrlich INVENTORY_INCOMPLETE, solange Reviews fehlen.
  UNKNOWN != PASS, SCAN != BETRIEFFUND, SCRIPTED != INSTALLED.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    # Skript-Modus: #460-Schatten reparieren (controller.py verdraengt
    # sonst das Namespace-Paket). Nur hier, niemals beim Import: andere
    # Module verlassen sich auf den Pfad, den fruehere Imports setzen.
    sys.path[:] = [
        p for p in sys.path
        if os.path.abspath(p if p else os.getcwd()) != _HERE
    ]
    sys.path.insert(0, os.path.dirname(_HERE))
from controller import node_inventory  # noqa: E402

IMPORT_RE = re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+([\w\.,\s]+)")
IMPORT_PLAIN_RE = re.compile(r"^\s*import\s+([\w\.]+)")
SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", "node_modules"}
STORAGE_EXT = (".json", ".jsonl", ".db", ".sqlite")


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        yield dirpath, filenames


def scan_import_graph(root):
    """Misst, welche lokalen Module von welchen Dateien importiert werden."""
    imports_of = {}
    py_files = []
    for dirpath, filenames in _walk(root):
        for name in filenames:
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                py_files.append(full)
    for full in py_files:
        mods = set()
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    match = IMPORT_RE.match(line)
                    if match:
                        base = match.group(1)
                        mods.add(base.split(".")[0])
                        for name in match.group(2).split(","):
                            name = name.strip().split(" ")[0].strip()
                            if name:
                                mods.add(base + "." + name)
                        continue
                    plain = IMPORT_PLAIN_RE.match(line)
                    if plain:
                        mods.add(plain.group(1).split(".")[0])
        except OSError:
            pass
        imports_of[full] = mods
    base_names = {os.path.basename(p)[:-3] for p in py_files}
    pkg_names = {
        os.path.basename(os.path.dirname(p)) for p in py_files
        if os.path.basename(os.path.dirname(p))
    }
    return py_files, imports_of, base_names, pkg_names


def component_id_for(root, path):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return "node:" + rel


def software_component(root, path, imported_by, is_test):
    size = os.path.getsize(path)
    active = bool(imported_by) or is_test
    return {
        "component_id": component_id_for(root, path),
        "name": os.path.basename(path),
        "kind": "software",
        "owner": "unassigned-pending-review",
        "evidence": {
            "source": "filesystem-scan:node_inventory_scan",
            "checked_on": utc_today(),
        },
        "eol_status": "unknown",
        "in_active_use": active,
        "measured": {
            "size_bytes": size,
            "imported_by": sorted(imported_by),
            "is_test_file": is_test,
        },
    }


def storage_component(root, path):
    size = os.path.getsize(path)
    return {
        "component_id": component_id_for(root, path),
        "name": os.path.basename(path),
        "kind": "storage",
        "owner": "unassigned-pending-review",
        "evidence": {
            "source": "filesystem-scan:node_inventory_scan",
            "checked_on": utc_today(),
        },
        "eol_status": "unknown",
        "in_active_use": True,
        "measured": {"size_bytes": size},
    }


def build_scanned_inventory(node_id, root, max_components=2000):
    """Baut ein Auditor-kompatibles Inventar aus Messwerten. Nur Lesen."""
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise NotADirectoryError(root)
    py_files, imports_of, base_names, pkg_names = scan_import_graph(root)
    stem_to_files = {}
    for full in py_files:
        stem_to_files.setdefault(os.path.basename(full)[:-3], []).append(full)
    components = []
    for full in sorted(py_files)[:max_components]:
        stem = os.path.basename(full)[:-3]
        importers = set()
        pkg_of_self = os.path.basename(os.path.dirname(full))
        for other, mods in imports_of.items():
            if other == full:
                continue
            if stem in mods and stem in base_names:
                importers.add(os.path.relpath(other, root).replace(os.sep, "/"))
            elif (
                pkg_of_self
                and (pkg_of_self + "." + stem) in mods
                and pkg_of_self in pkg_names
            ):
                importers.add(os.path.relpath(other, root).replace(os.sep, "/"))
        is_test = os.path.basename(full).startswith("test_")
        components.append(
            software_component(root, full, importers, is_test)
        )
    storage_seen = 0
    for dirpath, filenames in _walk(root):
        for name in filenames:
            if name.endswith(STORAGE_EXT) and storage_seen < (
                max_components - len(components)
            ):
                storage_seen += 1
                components.append(
                    storage_component(root, os.path.join(dirpath, name))
                )
    return {
        "node_id": node_id,
        "date": utc_today(),
        "reviewer": "node_inventory_scan (maschine, kein betreiber-review)",
        "components": components,
    }


def audit_scanned(inventory):
    """Fuehrt den fail-closed Auditor aus und angereichert das Ergebnis."""
    verdict = node_inventory.validate_inventory(inventory)
    verdict["scan_limits"] = (
        "COMPLETE ist nur die strukturelle auditor-pruefung:"
        " dienste/identitaeten/energie nicht gemessen, alle eol-status"
        " unknown, owner ausstehend. COMPLETE != BETRIEFFUND,"
        " REVIEW != ENTSCHEIDUNG"
    )
    return verdict


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mess-Scan -> Knoten-Inventar")
    parser.add_argument("root")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    inventory = build_scanned_inventory(args.node_id, args.root)
    verdict = audit_scanned(inventory)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(
                {"inventory": inventory, "verdict": verdict},
                handle, sort_keys=True, indent=1,
            )
    print(json.dumps(verdict, sort_keys=True))
    return 1 if verdict["decision"] == "REJECTED" else 0


if __name__ == "__main__":
    sys.exit(main())

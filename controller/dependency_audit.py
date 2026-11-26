"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Dependency-Audit (Issue #591): misst, welche deklarierten Abhaengig-
keiten (requirements.txt / requirements-dev.txt) im Bestand wirklich
per Python-Import verwendet werden. Das Modul ERZEUGT Evidenz, es
entscheidet NICHT: REPORT != DELETE, NICHT_GEFUNDEN != UNGENUTZT.

Verfahren (fail-closed):
- parse_requirements: Zeilen ohne Paketnamen, leere Namen oder
  ungueltige -r/-e/-f-Optionen ohne Ziel sind MESSFEHLER, kein Sturz
  ins Ungefunde.
- collect_py_imports: AST-basiertes Einsammeln der Top-Level-Modul-
  namen aller .py-Dateien unter dem Wurzelverzeichnis (kein Regex,
  kein exec). Verzeichnisse .git und __pycache__ werden ausgespart.
- audit: je deklariertem Paket ein Verdikt:
    GENUTZT               (>= 1 Import-Fundstelle, Pfade gedeckelt)
    NICHT_GEFUNDEN_IN_PY  (0 Import-Fundstellen; NICHT_GEFUNDEN
                          != UNGENUTZT: dynamische/extern genutzte
                          Abhaengigkeiten bleiben UNKNOWN)
  Nicht-.py-Nennungen (README, Workflows, Doku) werden als HINWEISE
  getrennt ausgewiesen, zaehlen NICHT als Nutzung.
- KEIN Netz, kein Daemon, keine Loesch- oder Schreiboperation auf
  beobachteten Dateien (ISOLATE_NOT_DESTROY).

Ehrliche Grenzen:
- MESSUNG_AM_BAUM != GESAMTWAHRHEIT: usage ausserhalb des gescannten
  Pfads (virtuelle Umgebungen, Startskripte ausserhalb des Repos,
  transitiv erwartete Abhaengigkeiten von Offline-Konsumenten) bleibt
  UNKNOWN und kann vom Bericht NICHT ausgeschlossen werden.
- PRUNE-ENTSCHEIDUNG IST BETREIBER: Das Modul empfiehlt NICHT
  autonom das Entfernen von Abhaengigkeiten; requirements-Dateien
  werden nicht veraendert.
- ENV_FEHLT-Klauseln: cryptography-abhaengige Bestandsteile sind von
  diesem Modul unberuehrt; dieses Modul selbst ist stdlib-only.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass, field

VERSION = "v91.dependency_audit.v1"

# Import-Name -> Distributionsname (nur dort noetig, wo sie abweichen).
IMPORT_NAME_OVERRIDES = {
    "PIL": "pillow",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
}

MAX_FUNDSTELLEN = 20
HINWEIS_SUFFIXES = (".md", ".yml", ".yaml", ".toml", "Dockerfile", ".json")


class DependencyAuditError(Exception):
    """Fail-closed Fehler des Dependency-Audits."""


@dataclass
class Requirement:
    name: str
    spezifikation: str
    quelle: str


@dataclass
class PaketBefund:
    name: str
    verdikt: str  # GENUTZT | NICHT_GEFUNDEN_IN_PY
    import_fundstellen: list = field(default_factory=list)
    hinweise_nicht_py: list = field(default_factory=list)


def parse_requirements(pfad: str) -> list[Requirement]:
    """Liest eine Requirements-Datei; fail-closed bei Strukturfehlern."""
    if not os.path.isfile(pfad):
        raise DependencyAuditError("REQUIREMENTS_FEHLT: " + pfad)
    anforderungen: list[Requirement] = []
    with open(pfad, "r", encoding="utf-8") as handle:
        for nummer, rohzeile in enumerate(handle, start=1):
            zeile = rohzeile.strip()
            if not zeile or zeile.startswith("#"):
                continue
            if zeile.startswith("-r"):
                ziel = zeile[2:].strip()
                if not ziel:
                    raise DependencyAuditError(
                        "REQUIREMENTS_UNGUELTIG Zeile %d: -r ohne Ziel" % nummer
                    )
                anforderungen.extend(parse_requirements(os.path.join(os.path.dirname(pfad), ziel)))
                continue
            if zeile.startswith("-"):
                # Andere Optionen (-e, -f, ...) sind hier Strukturfehler:
                # ihr Ziel ist keine messbare einfache Abhaengigkeit.
                raise DependencyAuditError(
                    "REQUIREMENTS_UNGUELTIG Zeile %d: Option nicht unterstuetzt: %s"
                    % (nummer, zeile)
                )
            name = zeile.split(";", 1)[0]
            for trenner in ("==", ">=", "<=", "~=", "!=", ">", "<", "===", "["):
                if trenner in name:
                    name = name.split(trenner, 1)[0]
            name = name.strip()
            if not name or "/" in name or " " in name:
                raise DependencyAuditError(
                    "REQUIREMENTS_UNGUELTIG Zeile %d: kein gueltiger Paketname: %s"
                    % (nummer, rohzeile.strip())
                )
            anforderungen.append(Requirement(name=name.lower(), spezifikation=zeile, quelle=pfad))
    return anforderungen


def _skip_verzeichnis(name: str) -> bool:
    return name in {".git", "__pycache__", "node_modules", ".tox", ".mypy_cache"}


def collect_py_imports(wurzel: str) -> dict:
    """AST-basiertes Einsammeln: Top-Level-Modul -> Dateipfade."""
    if not os.path.isdir(wurzel):
        raise DependencyAuditError("WURZEL_FEHLT: " + wurzel)
    funde: dict = {}
    for ordner, unterordner, dateien in os.walk(wurzel):
        unterordner[:] = [d for d in unterordner if not _skip_verzeichnis(d)]
        for datei in dateien:
            if not datei.endswith(".py"):
                continue
            pfad = os.path.join(ordner, datei)
            try:
                with open(pfad, "r", encoding="utf-8") as handle:
                    baum = ast.parse(handle.read(), filename=pfad)
            except (OSError, SyntaxError, UnicodeDecodeError) as fehler:
                raise DependencyAuditError(
                    "PY_UNLESBAR %s: %s" % (pfad, fehler)
                ) from fehler
            for knoten in ast.walk(baum):
                if isinstance(knoten, ast.Import):
                    for alias in knoten.names:
                        top = alias.name.split(".", 1)[0]
                        funde.setdefault(top, []).append(pfad)
                elif isinstance(knoten, ast.ImportFrom):
                    if knoten.module and knoten.level == 0:
                        top = knoten.module.split(".", 1)[0]
                        funde.setdefault(top, []).append(pfad)
    return funde


def _import_namen_fuer(paket: str) -> list:
    namen = [paket]
    for import_name, dist in IMPORT_NAME_OVERRIDES.items():
        if dist == paket:
            namen.append(import_name)
    return namen


def _hinweise_sammeln(wurzel: str, paket: str) -> list:
    """Nicht-.py-Nennungen als HINWEISE (keine Nutzungsevidenz)."""
    hinweise = []
    for ordner, unterordner, dateien in os.walk(wurzel):
        unterordner[:] = [d for d in unterordner if not _skip_verzeichnis(d)]
        for datei in dateien:
            if not (datei.endswith(HINWEIS_SUFFIXES) or datei == "Dockerfile"):
                continue
            pfad = os.path.join(ordner, datei)
            try:
                with open(pfad, "r", encoding="utf-8", errors="strict") as handle:
                    if paket in handle.read():
                        hinweise.append(pfad)
            except (OSError, UnicodeDecodeError):
                continue
    return sorted(hinweise)[:MAX_FUNDSTELLEN]


def audit(wurzel: str, requirements_pfad: str | None = None) -> dict:
    """Misst die Nutzung deklarierter Abhaengigkeiten. REPORT != DELETE."""
    anforderungen = parse_requirements(requirements_pfad or os.path.join(wurzel, "requirements.txt"))
    funde = collect_py_imports(wurzel)
    befunde = []
    for anforderung in anforderungen:
        import_pfade = sorted(
            {pfad for name in _import_namen_fuer(anforderung.name) for pfad in funde.get(name, [])}
        )
        if import_pfade:
            verdikt = "GENUTZT"
        else:
            verdikt = "NICHT_GEFUNDEN_IN_PY"
        befunde.append(
            PaketBefund(
                name=anforderung.name,
                verdikt=verdikt,
                import_fundstellen=import_pfade[:MAX_FUNDSTELLEN],
                hinweise_nicht_py=_hinweise_sammeln(wurzel, anforderung.name),
            )
        )
    return {
        "version": VERSION,
        "wurzel": os.path.abspath(wurzel),
        "requirements": os.path.abspath(requirements_pfad or os.path.join(wurzel, "requirements.txt")),
        "paketanzahl": len(befunde),
        "befunde": [
            {
                "paket": b.name,
                "verdikt": b.verdikt,
                "import_fundstellen": b.import_fundstellen,
                "anzahl_import_fundstellen": len(b.import_fundstellen),
                "hinweise_nicht_py": b.hinweise_nicht_py,
                "notiz": (
                    "NICHT_GEFUNDEN != UNGENUTZT: Nutzung ausserhalb des "
                    "gescannten Baums bleibt UNKNOWN; Entfernen aus "
                    "requirements ist BETREIBER-ENTSCHEIDUNG."
                    if b.verdikt == "NICHT_GEFUNDEN_IN_PY"
                    else "Nutzung per AST-Importnachweis belegt."
                ),
            }
            for b in befunde
        ],
        "grenzen": [
            "MESSUNG_AM_BAUM != GESAMTWAHRHEIT",
            "REPORT != DELETE",
            "HINWEIS != NUTZUNG",
            "NICHT_GEFUNDEN != UNGENUTZT",
        ],
    }


def _self_check() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        wurzel = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(wurzel, "pkg"))
        with open(os.path.join(wurzel, "requirements.txt"), "w", encoding="utf-8") as fh:
            fh.write("numpy>=1.26\nredis>=5.0\n")
        with open(os.path.join(wurzel, "pkg", "mod.py"), "w", encoding="utf-8") as fh:
            fh.write("import numpy\nprint(numpy.__name__)\n")
        bericht = audit(wurzel)
        befunde = {b["paket"]: b["verdikt"] for b in bericht["befunde"]}
        ok = befunde.get("numpy") == "GENUTZT" and befunde.get("redis") == "NICHT_GEFUNDEN_IN_PY"
        print(
            json.dumps(
                {
                    "mechanismus": "getestet",
                    "self_check": "PASS" if ok else "FAIL",
                    "echtes_repo": "NICHT_GEPRUEFT",
                },
                ensure_ascii=True,
            )
        )
        return 0 if ok else 1


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dependency_audit", description="V91 Dependency-Audit (Issue #591)")
    parser.add_argument("--self-check", action="store_true", help="Synthetischer Selbsttest (kein echtes Repo)")
    parser.add_argument("--path", default=".", help="Wurzelverzeichnis des Bestands")
    parser.add_argument("--requirements", default=None, help="Pfad zur Requirements-Datei (Default: <path>/requirements.txt)")
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    try:
        bericht = audit(args.path, args.requirements)
    except DependencyAuditError as fehler:
        print(json.dumps({"status": "MESSFEHLER", "fehler": str(fehler)}, ensure_ascii=True))
        return 1
    print(json.dumps(bericht, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Aktiver MAX-BEST-Arbeitszyklus (Core-Vertrag, Issue #592): gemeinsamer
Aufgaben-, Rechte-, Policy-, Mess- und Auditvertrag fuer den Verbund.
Core definiert NUR Vertrag und Pruefungen; die Laufzeit (Agathon) und
die Analyse (Aurelia/Prisma) bleiben eigene Bloecke (ROLLEN != CODE).

Disziplin (fail-closed):
- PHASENWECHSEL NUR MIT BELEG: kein Sprung, keine Rueckdatierung,
  keine Phase aus Behauptung (EVIDENZ != BEHAUPTUNG).
- STEUERAKTION NUR MIT EXPLIZITER CAPABILITY: unbekannte Peers,
  unbekannte Aktionen, abgelaufene oder widerrufene Identitaeten
  werden ABGELEHNT, nie stillschweigend erweitert.
- ABSCHALTEN == ISOLIEREN: keine Zerstoerung; Vollzug realer
  Eingriffe bleibt Betreiber-/Adapter-Aktion, dieses Modul
  entscheidet nur (ENTSCHEIDUNG != VOLLZUG).
- UNKNOWN BLEIBT UNKNOWN: fehlende Messwerte werden niemals als
  0, Erfolg oder Null ausgegeben.
- PEER-AUSFALL BLOCKIERT NICHT: lokale Auftraege laufen weiter.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple

PHASEN: Tuple[str, ...] = (
    "ERKANNT",
    "KOORDINIERT",
    "AUSGEFUEHRT",
    "GEMESSEN",
    "GELERNT",
)

# Steueraktionen gemaess #592; ABSCHALTEN ist vertraglich ISOLIEREN.
STEUERAKTIONEN: Tuple[str, ...] = (
    "KONFIGURIEREN",
    "PAUSIEREN",
    "BEGRENZEN",
    "ISOLIEREN",
    "NEUSTARTEN",
    "ERSETZEN",
    "ABSCHALTEN",
)

# Aktionen, die zusaetzlich eine dokumentierte Betreiber-Freigabe
# im Registry-Eintrag verlangen (keine Automation der Abschaltung).
BETREIBER_FREIGABE_PFLICHT: Tuple[str, ...] = ("ABSCHALTEN", "ERSETZEN")

UNBEKANNT = "UNKNOWN"


class VerbundVertragsError(Exception):
    """Vertragsverletzung: unzulaessiger Uebergang oder unzulaessige Aktion."""


# ---------------------------------------------------------------- Auftrag


def neuer_auftrag(quelle: str, beschreibung: str, faehigkeit: str) -> Dict[str, Any]:
    """Neuer Auftrag in Phase ERKANNT. Leere Angaben fail-closed."""
    for feld, wert in (("quelle", quelle), ("beschreibung", beschreibung), ("faehigkeit", faehigkeit)):
        if not isinstance(wert, str) or not wert.strip():
            raise VerbundVertragsError(f"unvollstaendiger Auftrag: {feld} fehlt")
    return {
        "quelle": quelle.strip(),
        "beschreibung": beschreibung.strip(),
        "faehigkeit": faehigkeit.strip(),
        "phase": "ERKANNT",
        "belege": [],
    }


def uebergehe_zu(auftrag: Mapping[str, Any], zielphase: str, beleg: str) -> Dict[str, Any]:
    """Phasenwechsel genau EINE Stufe weiter, NUR mit nicht-leerem Beleg."""
    if not isinstance(auftrag, Mapping) or auftrag.get("phase") not in PHASEN:
        raise VerbundVertragsError("Auftrag ohne gueltige Phase")
    if not isinstance(beleg, str) or not beleg.strip():
        raise VerbundVertragsError("Phasenwechsel ohne Beleg abgelehnt (BEWEIS != BEHAUPTUNG)")
    if zielphase not in PHASEN:
        raise VerbundVertragsError(f"unbekannte Phase: {zielphase}")
    ist = PHASEN.index(auftrag["phase"])
    if PHASEN.index(zielphase) != ist + 1:
        raise VerbundVertragsError(f"unzulaessiger Uebergang {auftrag['phase']} -> {zielphase}")
    ergebnis = dict(auftrag)
    ergebnis["phase"] = zielphase
    ergebnis["belege"] = list(auftrag.get("belege", [])) + [beleg.strip()]
    return ergebnis


def messung_fordert(auftrag: Mapping[str, Any]) -> None:
    """Phase GEMESSEN verlangt einen Ergebnis-Datensatz am Auftrag."""
    datensatz = auftrag.get("ergebnis")
    if not isinstance(datensatz, Mapping):
        raise VerbundVertragsError("Messung ohne Ergebnis-Datensatz unzulaessig")


# ---------------------------------------------------- Ergebnis-Datensatz


def ergebnis_datensatz(
    *,
    baseline: Any,
    messwert: Any,
    einheit: str,
    zeitraum: str,
    quelle: str,
    unsicherheit: Any = None,
    wirkung: List[str],
    artefakte: List[str],
) -> Dict[str, Any]:
    """Ergebnis-Datensatz gemaess #592 Kriterium 4.

    Fehlende Werte werden als UNKNOWN gefuehrt, NIEMALS als 0, null
    oder Erfolg. Einheit/Zeitraum/Quelle sind Pflicht-Text.
    """
    if not isinstance(einheit, str) or not einheit.strip():
        raise VerbundVertragsError("Messung ohne Einheit unzulaessig")
    if not isinstance(zeitraum, str) or not zeitraum.strip():
        raise VerbundVertragsError("Messung ohne Zeitraum unzulaessig")
    if not isinstance(quelle, str) or not quelle.strip():
        raise VerbundVertragsError("Messung ohne Quelle unzulaessig")
    if not isinstance(wirkung, list) or not wirkung:
        raise VerbundVertragsError("Messung ohne Wirkungsangabe unzulaessig")
    if not isinstance(artefakte, list):
        raise VerbundVertragsError("artefakte muss eine Liste sein")
    return {
        "baseline": baseline if baseline is not None else UNBEKANNT,
        "messwert": messwert if messwert is not None else UNBEKANNT,
        "einheit": einheit.strip(),
        "zeitraum": zeitraum.strip(),
        "quelle": quelle.strip(),
        "unsicherheit": unsicherheit if unsicherheit is not None else UNBEKANNT,
        "wirkung": list(wirkung),
        "artefakte": list(artefakte),
    }


def wirksamkeit(datensatz: Mapping[str, Any]) -> str:
    """Wirksamkeitsaussage NUR bei vollstaendiger Evidenz, sonst UNKNOWN."""
    if not isinstance(datensatz, Mapping):
        return UNBEKANNT
    if datensatz.get("messwert") in (None, UNBEKANNT):
        return UNBEKANNT
    if datensatz.get("baseline") in (None, UNBEKANNT):
        return UNBEKANNT
    return "MESSBAR_VERGLICHEN"


# ------------------------------------------------- Steueraktion (Adapter)


def pruefe_steueraktion(
    registry: Mapping[str, Any],
    *,
    peer_id: str,
    aktion: str,
    policy_version: str,
    ausloeser: str,
    wirkungsradius: str,
    rollback: str,
    jetzt: float,
) -> Dict[str, Any]:
    """Autorisierungs-Entscheidung fuer eine Steueraktion. Fail-closed.

    ENTSCHEIDUNG != VOLLZUG: dieses Modul fuehrt NICHTS aus.
    Gewaehrt wird NUR die angefragte Aktion, nie mehr
    (KEINE_STILLSCHWEIGENDE_RECHTEAUSWEITUNG).
    """
    grund = ""
    erlaubt = False
    peer: Optional[Mapping[str, Any]] = None
    if not isinstance(registry, Mapping):
        grund = "Registry fehlt"
    else:
        roh = registry.get("peers", {}).get(peer_id) if isinstance(registry.get("peers"), Mapping) else None
        peer = roh if isinstance(roh, Mapping) else None
        if peer is None:
            grund = f"Peer nicht registriert: {peer_id or 'LEER'}"
        elif aktion not in STEUERAKTIONEN:
            grund = f"unbekannte Aktion: {aktion}"
        elif not isinstance(peer.get("capabilities"), list) or aktion not in peer["capabilities"]:
            grund = f"Capability nicht gewaehrt: {aktion}"
        elif peer.get("widerrufen") is True:
            grund = "Identitaet widerrufen"
        elif not isinstance(peer.get("gueltig_bis"), (int, float)) or jetzt > peer["gueltig_bis"]:
            grund = "Identitaet abgelaufen"
        elif policy_version != registry.get("policy_version"):
            grund = "Policy-Version stimmt nicht ueberein"
        elif not isinstance(ausloeser, str) or not ausloeser.strip():
            grund = "Ausloesekriterium fehlt"
        elif not isinstance(wirkungsradius, str) or not wirkungsradius.strip():
            grund = "Wirkungsradius fehlt"
        elif not isinstance(rollback, str) or not rollback.strip():
            grund = "Rollback-Plan fehlt"
        elif aktion in BETREIBER_FREIGABE_PFLICHT and peer.get("freigabe_betreiber") is not True:
            grund = f"Betreiber-Freigabe fehlt fuer {aktion}"
        else:
            erlaubt = True

    entscheidung: Dict[str, Any] = {
        "peer_id": peer_id,
        "aktion": aktion,
        "erlaubt": erlaubt,
        "policy_version": policy_version,
        "grund": grund if grund else "AUTORISIERT",
    }
    if aktion == "ABSCHALTEN" and erlaubt:
        entscheidung["semantik"] = "ISOLIEREN_NICHT_ZERSTOEREN"
    return audit_eintrag(entscheidung)


def audit_eintrag(entscheidung: Mapping[str, Any]) -> Dict[str, Any]:
    """Jede Entscheidung erhaelt Identitaet, Ziel, Policy, Grund, Audit."""
    eintrag = dict(entscheidung)
    eintrag["audit"] = "VERBUND-AUDIT:" + json.dumps(
        {
            "peer": eintrag.get("peer_id"),
            "aktion": eintrag.get("aktion"),
            "erlaubt": eintrag.get("erlaubt"),
            "policy": eintrag.get("policy_version"),
            "grund": eintrag.get("grund"),
        },
        sort_keys=True,
    )
    return eintrag


# ------------------------------------------------------ Peer-Ausfall


def verarbeite_statusmeldungen(
    auftraege: List[Mapping[str, Any]],
    statusmeldungen: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Lokale Schleife: fehlende Peers blockieren NIE lokale Arbeit."""
    ergebnis: List[Dict[str, Any]] = []
    for auftrag in auftraege:
        kopie = dict(auftrag)
        status = statusmeldungen.get(auftrag.get("quelle", ""))
        if status is None:
            kopie["peer_status"] = UNBEKANNT
            kopie["lokale_arbeit"] = "WEITERLAUFEND"
        else:
            kopie["peer_status"] = status
        ergebnis.append(kopie)
    return ergebnis


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MAX-BEST Verbund-Arbeitszyklus (Core-Vertrag)")
    parser.add_argument("--self-check", action="store_true", help="Strukturpruefung des Vertrags")
    args = parser.parse_args(argv)
    if args.self_check:
        print("PHASEN:", "|".join(PHASEN))
        print("STEUERAKTIONEN:", "|".join(STEUERAKTIONEN))
        print("ABSCHALT_SEMANTIK: ISOLIEREN_NICHT_ZERSTOEREN")
        print("UNBEKANNT_BLEIBT:", UNBEKANNT)
        print("ENTSCHEIDUNG != VOLLZUG: DIESER VERTRAG FUEHRT NICHTS AUS")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Resource-Redirection & Wirkungsrechner (FREMD-ENTWURF-MODELL,
V91-CONTRIB-2026-11-27-RRR): Mittel-Bilanz je Massnahme und
Umleitungsrechnung (schrittweiser Abbau fossiler Fehlanreize ->
VERPFLICHTENDER Sozialpuffer VOR jeder Verteilung -> gewichtete
Aufteilung auf Renaturierungs-, Wasser- und Kreislaufwirtschafts-
Module), strikt getrennt nach FAKT / ANNAHME / NICHT_GEPRUEFT.

Provenienz und Nachmessung (27.11.2026): Entwurf eines externen
Modells, via Sebastian (Betreiber-Relay) uebergeben. Kein Duplikat:
controller/wirkungs_assessment misst ledger-gestuetzte Indikatoren
(Messseite, KEINE Mittel-/EUR-Dimension), controller/resource_
admission misst lokale Host-Ressourcen (CPU/RAM, KEINE Geldstroeme).
Dieses Modul ist die Geld-Gegenrechnung (MITTEL-SEITE) dazu.

UEBERNAHME-AENDERUNGEN am Entwurf (offengelegt, NACHTRAG != ENTWURF):
- ASCII-Transliteration (der Relay-Text trug Mojo-Bake in Quotes,
  Umlaut-Identifikatoren und einem entstellten __name__-Guard).
- Referenzwertbasis nachgemessen und korrigiert: die behauptete
  "EEA-Auswertung 43 Mrd EUR 2024" wurde NICHT bestaetigt. Oeffentliche
  Messung 2026 (FOES/Bertelsmann, Klima-Subventionsbericht): 66,2 Mrd
  EUR (teilweise) klimaschaedlige Subventionen 2024, davon 38,4 Mrd
  EUR eindeutig klimaschaedlich. Das Standardbeispiel nutzt 38,4 Mrd
  als ANNAHME mit Quellenangabe, nicht als FAKT.
- Sektor-Validierung fail-closed nachgetragen (Literal prueft zur
  Laufzeit nichts), Ziel-Statuskette wie im Entwurf verriegelt.

Regeln (fail-closed):
- Status nur FAKT / ANNAHME / NICHT_GEPRUEFT. FAKT erfordert
  Messwert UND Quelle; ANNAHME erfordert benannte Annahme.
- Erfuellungsgrad wird NUR aus FAKT-Eintraegen berechnet; ohne
  Messwert bleibt er None (NICHT_GEPRUEFT wird nie durch 0 ersetzt).
- Der Sozialpuffer (Haushaltsausgleich, Qualifizierung, faire
  Beschaeftigung) wird VOR jeder Modul-Verteilung abgezogen:
  SOZIAL_SCHUTZ_VOR_PROJEKT. Kein Puffer -> keine Verteilung
- Geldfluesse sind NICHT autorisiert: RECHENMODELL != HAUSHALT,
  RECHENMODELL != POLITISCHER BESCHLUSS, RECHNEN != VOLLZUG.
  Dieses Modul leitet keine realen Bundesmittel um und greift
  auf kein fremdes System zu (RAGNAROEK: erst Besseres rechnen).

Ehrliche Grenzen: Stueckkosten, Abbauraten und Sozialquoten sind
Richtwerte (ANNAHME), bis echte Projekt- und Foerderdaten eingesetzt
werden. WIRKUNG_GERECHNET != WIRKUNG_GEMESSEN; fuer echte Messwerte
bleibt controller/wirkungs_assessment (R2-R5-Messkette) allein
verbindlich (KANON == MESSUNG != MITTELBILANZ).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # Skript-Modus: #605-Muster
    _ROOT = str(Path(__file__).resolve().parents[1])
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from typing import Literal  # noqa: E402

EvidenzStatus = Literal["FAKT", "ANNAHME", "NICHT_GEPRUEFT"]
ERLAUBTE_EVIDENZ: tuple[EvidenzStatus, ...] = ("FAKT", "ANNAHME", "NICHT_GEPRUEFT")
ERLAUBTE_SEKTOREN: tuple[str, ...] = ("RENATURIERUNG", "WASSER", "KREISLAUFWIRTSCHAFT")


def _require_finite_number(value: object, field_name: str) -> None:
    """Reject bools, non-numbers, NaN and infinities before calculations."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number (Fail-Closed).")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{field_name} must be a finite number (Fail-Closed).")

SCHEMA_VERSION = "v91-resource-redirection-1.0"
QUELLE_REFERENZ_2024 = (
    "FOES/Bertelsmann-Stiftung, Klima-Subventionsbericht 2026: "
    "38,4 Mrd EUR eindeutig klimaschaedliche Subventionen 2024 "
    "(66,2 Mrd inkl. teilweise klimaschaedlicher); ANNAHME-Referenz"
)


@dataclass(frozen=True)
class WirkungsMassnahme:
    """Eine Massnahme mit Mitteln, Zielwert und Evidenz-Status."""

    massnahme_id: str
    bereich: str
    titel: str
    mittel_eur: float
    erwartete_wirkung_einheit: str
    zielwert: float
    ist_wert: float | None
    status: EvidenzStatus
    quelle: str = ""
    soziale_absicherung: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name, value in (("mittel_eur", self.mittel_eur), ("zielwert", self.zielwert)):
            _require_finite_number(value, name)
        if self.ist_wert is not None:
            _require_finite_number(self.ist_wert, "ist_wert")
        if self.status not in ERLAUBTE_EVIDENZ:
            raise ValueError(f"Ungueltiger EvidenzStatus (Fail-Closed): {self.status!r}")
        if self.mittel_eur < 0 or self.zielwert <= 0:
            raise ValueError("Mittel muessen >= 0 und Zielwert > 0 sein (Fail-Closed).")
        if self.status == "FAKT":
            if self.ist_wert is None or not self.quelle.strip():
                raise ValueError(
                    "Status 'FAKT' erfordert gemessenen ist_wert und Quelle (Fail-Closed)."
                )
        if self.status == "ANNAHME" and not self.quelle.strip():
            raise ValueError(
                "Status 'ANNAHME' erfordert eine benannte Annahme in quelle (Fail-Closed)."
            )


@dataclass(frozen=True)
class UmleitungsQuelle:
    """Schrittweiser Abbau fossiler Fehlanreize mit sozialer Absicherung."""

    quelle_id: str
    bezeichnung: str
    basis_subvention_eur: float
    abbau_anteil: float
    sozial_absicherung_anteil: float
    status: EvidenzStatus
    nachweis: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("basis_subvention_eur", self.basis_subvention_eur),
            ("abbau_anteil", self.abbau_anteil),
            ("sozial_absicherung_anteil", self.sozial_absicherung_anteil),
        ):
            _require_finite_number(value, name)
        if self.status not in ERLAUBTE_EVIDENZ:
            raise ValueError(f"Ungueltiger Status (Fail-Closed): {self.status!r}")
        if self.basis_subvention_eur < 0:
            raise ValueError("Basis-Subvention darf nicht negativ sein (Fail-Closed).")
        if not (0.0 <= self.abbau_anteil <= 1.0):
            raise ValueError("abbau_anteil muss in [0.0, 1.0] liegen (Fail-Closed).")
        if not (0.0 <= self.sozial_absicherung_anteil <= 1.0):
            raise ValueError(
                "sozial_absicherung_anteil muss in [0.0, 1.0] liegen (Fail-Closed)."
            )
        if self.status in ("FAKT", "ANNAHME") and not self.nachweis.strip():
            raise ValueError(
                "Status " + repr(self.status) + " erfordert einen Nachweis (Fail-Closed)."
            )

    @property
    def brutto_umleitung_eur(self) -> float:
        return self.basis_subvention_eur * self.abbau_anteil

    @property
    def sozial_puffer_eur(self) -> float:
        return self.brutto_umleitung_eur * self.sozial_absicherung_anteil

    @property
    def netto_projekt_budget_eur(self) -> float:
        return self.brutto_umleitung_eur - self.sozial_puffer_eur


@dataclass(frozen=True)
class ZielModul:
    """Renaturierungs-, Wasser- oder Kreislaufwirtschafts-Modul."""

    modul_id: str
    sektor: str
    titel: str
    kosten_pro_einheit_eur: float
    wirkung_einheit: str
    gewichtung_anteil: float
    status: EvidenzStatus
    nachweis: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name, value in (
            ("kosten_pro_einheit_eur", self.kosten_pro_einheit_eur),
            ("gewichtung_anteil", self.gewichtung_anteil),
        ):
            _require_finite_number(value, name)
        if self.status not in ERLAUBTE_EVIDENZ:
            raise ValueError(f"Ungueltiger Status (Fail-Closed): {self.status!r}")
        if self.sektor not in ERLAUBTE_SEKTOREN:
            raise ValueError(
                f"sektor muss einer von {ERLAUBTE_SEKTOREN} sein (Fail-Closed)."
            )
        if self.kosten_pro_einheit_eur <= 0:
            raise ValueError("kosten_pro_einheit_eur muss > 0 sein (Fail-Closed).")
        if not (0.0 <= self.gewichtung_anteil <= 1.0):
            raise ValueError("gewichtung_anteil muss in [0.0, 1.0] liegen (Fail-Closed).")
        if self.status in ("FAKT", "ANNAHME") and not self.nachweis.strip():
            raise ValueError(
                "Status " + repr(self.status) + " erfordert einen Nachweis (Fail-Closed)."
            )


def berechne_wirkungsbilanz(massnahmen: list[WirkungsMassnahme]) -> str:
    """Nach EvidenzStatus getrennte Wirkungs- und Mittelbilanz als JSON."""
    gesamt_mittel = sum(m.mittel_eur for m in massnahmen)
    belegte_mittel = sum(m.mittel_eur for m in massnahmen if m.status == "FAKT")
    ungepruefte_mittel = sum(m.mittel_eur for m in massnahmen if m.status != "FAKT")

    eintraege = []
    for m in massnahmen:
        erfuellungsgrad = (
            round(m.ist_wert / m.zielwert, 4)
            if (m.status == "FAKT" and m.ist_wert is not None)
            else None
        )
        eintraege.append(
            {
                "massnahme_id": m.massnahme_id,
                "bereich": m.bereich,
                "titel": m.titel,
                "mittel_eur": m.mittel_eur,
                "zielwert": m.zielwert,
                "ist_wert": m.ist_wert,
                "einheit": m.erwartete_wirkung_einheit,
                "erfuellungsgrad": erfuellungsgrad,
                "status": m.status,
                "quelle": m.quelle,
                "soziale_absicherung": m.soziale_absicherung,
                "tags": list(m.tags),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gesamt_mittel_eur": round(gesamt_mittel, 2),
        "belegte_mittel_eur": round(belegte_mittel, 2),
        "ungepruefte_oder_annahme_mittel_eur": round(ungepruefte_mittel, 2),
        "eintraege": eintraege,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def berechne_umleitung(
    quellen: list[UmleitungsQuelle],
    module: list[ZielModul],
) -> dict[str, object]:
    """Sozialpuffer, Nettomittel je Modul und erreichbare Wirkungs-Einheiten."""
    if not module:
        raise ValueError("Mindestens ein ZielModul ist erforderlich (Fail-Closed).")

    summe_gewichte = sum(m.gewichtung_anteil for m in module)
    if summe_gewichte <= 0.0:
        raise ValueError("Summe der Modul-Gewichtungen muss > 0 sein (Fail-Closed).")

    brutto_gesamt = sum(q.brutto_umleitung_eur for q in quellen)
    sozial_gesamt = sum(q.sozial_puffer_eur for q in quellen)
    netto_gesamt = sum(q.netto_projekt_budget_eur for q in quellen)

    modul_ergebnisse: list[dict[str, object]] = []
    for m in module:
        anteil_normiert = m.gewichtung_anteil / summe_gewichte
        budget_eur = netto_gesamt * anteil_normiert
        einheiten = budget_eur / m.kosten_pro_einheit_eur
        modul_ergebnisse.append(
            {
                "modul_id": m.modul_id,
                "sektor": m.sektor,
                "titel": m.titel,
                "status": m.status,
                "budget_eur": round(budget_eur, 2),
                "einheiten": round(einheiten, 2),
                "wirkung_einheit": m.wirkung_einheit,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "brutto_umleitung_eur": round(brutto_gesamt, 2),
        "sozial_absicherung_eur": round(sozial_gesamt, 2),
        "netto_projekt_budget_eur": round(netto_gesamt, 2),
        "module": modul_ergebnisse,
        "referenz": QUELLE_REFERENZ_2024,
    }


def standard_szenario_beispiel() -> dict[str, object]:
    """Beispielrechnung mit Richtwerten (klar als ANNAHME markiert).

    Basis 38,4 Mrd EUR (eindeutig klimaschaedliche Subventionen 2024
    laut FOES/Bertelsmann-Nachmessung) als ANNAHME-Referenz; Abbaurate
    10 %, Sozialquote 35 % sind Modellannahmen, KEINE Messwerte.
    """
    quellen = [
        UmleitungsQuelle(
            quelle_id="FOSSIL-DE-2024",
            bezeichnung=(
                "Schrittweiser Abbau fossiler Fehlanreize "
                "(Richtwert-Basis, nachgemessene Referenz)"
            ),
            basis_subvention_eur=38_400_000_000.0,
            abbau_anteil=0.10,
            sozial_absicherung_anteil=0.35,
            status="ANNAHME",
            nachweis=QUELLE_REFERENZ_2024 + "; Abbau 10 % und Sozialquote 35 % sind Modellannahmen",
        )
    ]
    module = [
        ZielModul(
            modul_id="MOD-MOOR-BODEN",
            sektor="RENATURIERUNG",
            titel="Moorwiedervernaessung & Bodenaufbau",
            kosten_pro_einheit_eur=15_000.0,
            wirkung_einheit="Hektar",
            gewichtung_anteil=0.40,
            status="ANNAHME",
            nachweis="Modell-Kostenrichtwert je Hektar",
            tags=("moor", "boden"),
        ),
        ZielModul(
            modul_id="MOD-WASSER-RUECKHALT",
            sektor="WASSER",
            titel="Wasserrueckhalt, Auen & Aufbereitung",
            kosten_pro_einheit_eur=2.50,
            wirkung_einheit="m3 Rueckhaltevolumen",
            gewichtung_anteil=0.35,
            status="NICHT_GEPRUEFT",
            tags=("wasser", "speicher"),
        ),
        ZielModul(
            modul_id="MOD-KREISLAUF-REP",
            sektor="KREISLAUFWIRTSCHAFT",
            titel="Reparatur-, Aufbereitungs- & Qualifizierungszentren",
            kosten_pro_einheit_eur=45_000.0,
            wirkung_einheit="Qualifizierungs-/Arbeitsplatzjahr",
            gewichtung_anteil=0.25,
            status="NICHT_GEPRUEFT",
            tags=("kreislauf", "qualifizierung"),
        ),
    ]
    return berechne_umleitung(quellen, module)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="resource_redirection",
        description=(
            "Mittel-Bilanz und Umleitungsrechnung mit Status-Trennung"
            " (FAKT/ANNAHME/NICHT_GEPRUEFT). Rechenmodell, kein Vollzug."
        ),
    )
    parser.add_argument(
        "--beispiel", action="store_true",
        help="Standard-Szenario (ANNAHME-Richtwerte) als JSON ausgeben",
    )
    parser.add_argument(
        "--eingabe", default=None,
        help="Pfad zu einem Szenario-JSON {quellen: [...], module: [...]}",
    )
    args = parser.parse_args(argv)

    if args.beispiel:
        print(json.dumps(standard_szenario_beispiel(), ensure_ascii=False, indent=2))
        return 0
    if args.eingabe:
        try:
            with open(args.eingabe, "r", encoding="utf-8") as handle:
                daten = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"error": f"eingabe unlesbar: {exc}"}))
            return 1
        try:
            quellen = [
                UmleitungsQuelle(
                    quelle_id=q["quelle_id"],
                    bezeichnung=q["bezeichnung"],
                    basis_subvention_eur=float(q["basis_subvention_eur"]),
                    abbau_anteil=float(q["abbau_anteil"]),
                    sozial_absicherung_anteil=float(q["sozial_absicherung_anteil"]),
                    status=q["status"],
                    nachweis=q.get("nachweis", ""),
                )
                for q in daten.get("quellen", [])
            ]
            module = [
                ZielModul(
                    modul_id=m["modul_id"],
                    sektor=m["sektor"],
                    titel=m["titel"],
                    kosten_pro_einheit_eur=float(m["kosten_pro_einheit_eur"]),
                    wirkung_einheit=m["wirkung_einheit"],
                    gewichtung_anteil=float(m["gewichtung_anteil"]),
                    status=m["status"],
                    nachweis=m.get("nachweis", ""),
                )
                for m in daten.get("module", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            print(json.dumps({"error": f"szenario ungueltig (Fail-Closed): {exc}"}))
            return 1
        print(json.dumps(berechne_umleitung(quellen, module), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

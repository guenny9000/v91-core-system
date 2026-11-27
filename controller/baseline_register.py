#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Baseline-Register je Kennzahl (Stufe-D-Luecke des Verbund-Stufen-Audits
#599/#601: 'Baseline/Vorher-Nachher je Kennzahl nicht flaechendeckend';
Protokoll #417 Abschnitt 3/4: Messplan verlangt je Kennzahl boundary,
baseline/after-Fenster, workload-Nenner und Kalibrierungsstatus).

Zweck: EIN append-only Register (JSONL), das die Vorher-Messreihe je
Kennzahl so aufzeichnet, dass spaetere Nachher-Messungen gegen DIESELBE
registrierte Baseline verglichen werden (Vorher-Nachher-Pflicht des
Dauerprotokolls). Kein zweites Impact-Modul (NO_DUPLICATE_SYSTEMS):
Parsen, DQI, Schwellenvalidierung und der eigentliche Periodenvergleich
bleiben allein in controller/impact.py; dieses Modul speichert, prueft
Grenz-/Workload-Konsistenz und ruft compute_impact auf.

Regeln (fail-closed):
- Eine Baseline wird nur registriert, wenn die Messreihe die Gates von
  impact.py besteht (tz-bewusste Zeitstempel, endliche Werte, bekannte
  source_type, min_samples, dqi_min). Sonst NICHT_REGISTRIERT mit
  Gruenden, NICHTS wird angehaengt (UNKNOWN wird nie als brauchbar
  ausgegeben).
- Ein Vergleich wird nur durchgefuehrt, wenn Kennzahl, Systemgrenze UND
  Workload-Einheit mit der registrierten Basale uebereinstimmen
  (Protokoll Abschnitt 4: gleiche Grenze, gleicher Nenner); jede
  Abweichung ist NICHT_VERGLEICHBAR, kein stiller Fallback.
- Bei mehreren Eintraegen je Kennzahl gilt der NEUESTE (append-only,
  aeltere bleiben unveraendert lesbar; ISOLATE_NOT_DESTROY).
- Kaputte Registerzeilen stoppen jeden Zugriff (fail-closed, nie
  still uebersprungen).

Ehrliche Grenzen:
- REGISTER != MESSPFAD: echte Baselines brauchen echte Messdaten
  (Issue #101/#103 bleiben Betreiber-/Laufzeit-Arbeit).
- BASELINE == FENSTERMITTEL: der gespeicherte Wert ist ein Mittel des
  erfassten Fensters, keine Wahrheit ueber die Anlage.
- VERGLEICH != UNABHAENIG_VERIFIZIERT; VALID bleibt Berechnungs-VALID
  wie in impact.py. Werkstatt-Vorher-Nachher ersetzt keine unabhaengige
  Gegenpruefung (#6).
- Kalibrierung wird nur als Referenz gespeichert (CALIBRATED != ACCURATE,
  REGISTRY != KALIBRIERUNG); Workload-NORMALISIERUNG bleibt allein in
  controller/workload_norm.py, hier wird nur die Einheitengeichheit
  geprueft (WINDOW == ANGABE != BEWEIS).
- Kein Daemon, kein Netzwerk, keine Zustandsaenderung an Sensoren.
  SCRIPTED != RUNNING.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
import sys
import time
from typing import Any, Dict, List, Optional

try:  # Paket-Import (Tests/CI starten ab Wurzel)
    from controller.impact import (
        _dqi,
        _parse,
        _validate_thresholds,
        compute_impact,
        load_csv,
    )
except ImportError:  # Skript-Modus: python controller/baseline_register.py
    # impact.py nutzt 'from ledger import HashChainLedger'; ledger.py liegt
    # in controller/ und ist nur erreichbar, wenn controller/ auf sys.path
    # liegt. Der Ordner wird NUR ANGEHAENGT, nie vorne eingefuegt, damit er
    # das Paket 'controller' nicht verdraengt (#460-Schatten-Lektion,
    # gleiches Muster wie workload_norm.py).
    _SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
    if _SCRIPT_DIR not in sys.path:
        sys.path.append(_SCRIPT_DIR)
    from impact import (  # type: ignore
        _dqi,
        _parse,
        _validate_thresholds,
        compute_impact,
        load_csv,
    )

VERSION = "v91.baseline_register.v1"
BASELINE_REGISTRIERT = "BASELINE_REGISTRIERT"
NICHT_REGISTRIERT = "NICHT_REGISTRIERT"
NICHT_GEFUNDEN = "NICHT_GEFUNDEN"
NICHT_VERGLEICHBAR = "NICHT_VERGLEICHBAR"
CALIBRATION_STATUSSE = (
    "UNKNOWN",
    "MISSING_REFERENCE",
    "REFERENCE_PRESENT_NOT_VERIFIED",
)
MAX_CALIBRATION_REF = 2048


class BaselineRegisterError(ValueError):
    """Schema-/Verletzungsfehler im Register-Zugriff (fail-closed)."""


def _jetzt_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineRegisterError(field + " must be a non-empty string")
    return value.strip()


def _validiere_meta(
    kennzahl: Any,
    unit: Any,
    systemgrenze: Any,
    workload_einheit: Any,
    calibration_ref: Any,
    calibration_status: Any,
) -> Dict[str, Any]:
    """Feldpruefung Messplan (Protokoll Abschnitt 3), fail-closed."""
    _require_nonempty_str(kennzahl, "kennzahl")
    _require_nonempty_str(unit, "unit")
    _require_nonempty_str(systemgrenze, "systemgrenze")
    if workload_einheit is not None:
        _require_nonempty_str(workload_einheit, "workload_einheit")
    if calibration_ref is not None:
        _require_nonempty_str(calibration_ref, "calibration_ref")
        if len(calibration_ref.strip()) > MAX_CALIBRATION_REF:
            raise BaselineRegisterError(
                "calibration_ref must be at most 2048 characters"
            )
        calibration_ref = calibration_ref.strip()
    if calibration_status is not None:
        if not isinstance(calibration_status, str) or (
            calibration_status not in CALIBRATION_STATUSSE
        ):
            raise BaselineRegisterError(
                "calibration_status must be one of " + ", ".join(CALIBRATION_STATUSSE)
            )
        # Konsistenzregeln wie measurement_store (#576): kein Status ohne
        # und kein Referenz-Status ohne Referenz.
        if calibration_status == "REFERENCE_PRESENT_NOT_VERIFIED" and calibration_ref is None:
            raise BaselineRegisterError(
                "calibration_status REFERENCE_PRESENT_NOT_VERIFIED requires calibration_ref"
            )
        if calibration_status == "MISSING_REFERENCE" and calibration_ref is not None:
            raise BaselineRegisterError(
                "calibration_status MISSING_REFERENCE must not carry calibration_ref"
            )
    return {
        "kennzahl": kennzahl.strip(),
        "unit": unit.strip(),
        "systemgrenze": systemgrenze.strip(),
        "workload_einheit": workload_einheit.strip() if isinstance(workload_einheit, str) else None,
        "calibration_ref": calibration_ref,
        "calibration_status": calibration_status,
    }


def _lade_eintraege(register_path: str) -> List[Dict[str, Any]]:
    """Append-only-Register lesen; kaputte Zeile stoppt alles."""
    pfad = pathlib.Path(register_path)
    if not pfad.exists():
        return []
    eintraege: List[Dict[str, Any]] = []
    with pfad.open(encoding="utf-8") as handle:
        for nummer, zeile in enumerate(handle, start=1):
            if not zeile.strip():
                raise BaselineRegisterError(
                    "REGISTER_ZEILE_LEER: " + str(nummer)
                )
            try:
                eintrag = json.loads(zeile)
            except json.JSONDecodeError as fehler:
                raise BaselineRegisterError(
                    "REGISTER_ZEILE_UNGUELTIG: " + str(nummer) + " (" + str(fehler) + ")"
                ) from fehler
            if not isinstance(eintrag, dict) or eintrag.get("schema_version") != VERSION:
                raise BaselineRegisterError(
                    "REGISTER_SCHEMA_UNBEKANNT: " + str(nummer)
                )
            if eintrag.get("type") != "baseline":
                raise BaselineRegisterError(
                    "REGISTER_TYP_UNERWARTET: " + str(nummer)
                )
            eintraege.append(eintrag)
    return eintraege


def register_baseline(
    register_path: str,
    kennzahl: str,
    unit: str,
    higher_is_worse: bool,
    baseline_rows: List[Dict[str, Any]],
    systemgrenze: str,
    workload_einheit: Optional[str] = None,
    calibration_ref: Optional[str] = None,
    calibration_status: Optional[str] = None,
    min_samples: Optional[int] = None,
    dqi_min: Optional[float] = None,
    noise_factor: Optional[float] = None,
) -> Dict[str, Any]:
    """Vorher-Messreihe je Kennzahl registrieren (nur bei Gate-Bestehen)."""
    thresholds = _validate_thresholds(min_samples, dqi_min, noise_factor)  # REUSE
    if not isinstance(higher_is_worse, bool):
        raise BaselineRegisterError("higher_is_worse must be a bool")
    meta = _validiere_meta(
        kennzahl, unit, systemgrenze, workload_einheit, calibration_ref, calibration_status
    )
    eintraege = _lade_eintraege(register_path)  # Kaputte Datei stoppt hier.
    samples, abgewiesen = _parse(baseline_rows)  # REUSE: naive ts abgelehnt
    gruende: List[str] = []
    if len(samples) < thresholds["min_samples"]:
        gruende.append("TOO_FEW_BASELINE_SAMPLES")
    dqi = _dqi(samples, abgewiesen)  # REUSE
    if dqi < thresholds["dqi_min"]:
        gruende.append("LOW_DQI")
    ergebnis: Dict[str, Any] = {
        "schema_version": VERSION,
        "status": NICHT_REGISTRIERT if gruende else BASELINE_REGISTRIERT,
        "kennzahl": meta["kennzahl"],
        "gruende": gruende,
        "n_baseline": len(samples),
        "abgewiesen": abgewiesen,
        "dqi": dqi,
        "thresholds": thresholds,
    }
    if gruende:
        return ergebnis
    fenster_start = min(s[0] for s in samples)
    fenster_ende = max(s[0] for s in samples)
    eintrag = {
        "schema_version": VERSION,
        "type": "baseline",
        "registriert_am": _jetzt_utc(),
        "kennzahl": meta["kennzahl"],
        "unit": meta["unit"],
        "higher_is_worse": higher_is_worse,
        "systemgrenze": meta["systemgrenze"],
        "workload_einheit": meta["workload_einheit"],
        "calibration_ref": meta["calibration_ref"],
        "calibration_status": meta["calibration_status"],
        "thresholds": thresholds,
        "n_baseline": len(samples),
        "abgewiesen": abgewiesen,
        "dqi": dqi,
        "fenster_start": fenster_start.isoformat(),
        "fenster_ende": fenster_ende.isoformat(),
        "baseline_mean": round(statistics.mean(s[1] for s in samples), 6),
        "baseline_reihe": [
            {"timestamp": s[0].isoformat(), "value": s[1], "source_type": s[2]}
            for s in samples
        ],
    }
    with pathlib.Path(register_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(eintrag, sort_keys=True, ensure_ascii=True) + "\n")
    ergebnis["baseline_mean"] = eintrag["baseline_mean"]
    ergebnis["fenster_start"] = eintrag["fenster_start"]
    ergebnis["fenster_ende"] = eintrag["fenster_ende"]
    ergebnis["registriert_am"] = eintrag["registriert_am"]
    return ergebnis


def vergleiche_gegen_baseline(
    register_path: str,
    kennzahl: str,
    after_rows: List[Dict[str, Any]],
    systemgrenze: str,
    workload_einheit: Optional[str] = None,
    min_samples: Optional[int] = None,
    dqi_min: Optional[float] = None,
    noise_factor: Optional[float] = None,
) -> Dict[str, Any]:
    """Nachher-Messreihe gegen die NEUESTE Baseline der Kennzahl vergleichen."""
    _require_nonempty_str(kennzahl, "kennzahl")
    _require_nonempty_str(systemgrenze, "systemgrenze")
    if workload_einheit is not None:
        _require_nonempty_str(workload_einheit, "workload_einheit")
    eintraege = _lade_eintraege(register_path)
    treffer = [e for e in eintraege if e.get("kennzahl") == kennzahl.strip()]
    if not treffer:
        return {
            "schema_version": VERSION,
            "status": NICHT_GEFUNDEN,
            "kennzahl": kennzahl.strip(),
            "gruende": ["KENNZAHL_NICHT_IM_REGISTER"],
        }
    basis = treffer[-1]  # append-only: der neueste Eintrag gilt
    gruende: List[str] = []
    if systemgrenze.strip() != basis["systemgrenze"]:
        gruende.append("SYSTEMGRENZE_ABWEICHEND")
    if (workload_einheit or None) != (basis.get("workload_einheit") or None):
        gruende.append("WORKLOAD_EINHEIT_ABWEICHEND")
    if gruende:
        return {
            "schema_version": VERSION,
            "status": NICHT_VERGLEICHBAR,
            "kennzahl": basis["kennzahl"],
            "gruende": gruende,
            "baseline_registriert_am": basis["registriert_am"],
        }
    # Schwellen: Caller-Parameter, sonst die registrierten (beides im
    # Ergebnis aufgezeichnet; REUSE impact._validate_thresholds fuer die
    # Caller-Pruefung).
    if min_samples is None:
        min_samples = basis["thresholds"]["min_samples"]
    if dqi_min is None:
        dqi_min = basis["thresholds"]["dqi_min"]
    if noise_factor is None:
        noise_factor = basis["thresholds"]["noise_factor"]
    _validate_thresholds(min_samples, dqi_min, noise_factor)
    vergleich = compute_impact(  # REUSE: Vergleich bleibt allein in impact.py
        measure=basis["kennzahl"],
        baseline_rows=basis["baseline_reihe"],
        after_rows=after_rows,
        unit=basis["unit"],
        higher_is_worse=basis["higher_is_worse"],
        min_samples=min_samples,
        dqi_min=dqi_min,
        noise_factor=noise_factor,
    )
    return {
        "schema_version": VERSION,
        "status": vergleich["status"],
        "kennzahl": basis["kennzahl"],
        "gruende": vergleich["flags"],
        "vergleich": vergleich,
        "baseline_registriert_am": basis["registriert_am"],
        "baseline_fenster": {
            "start": basis["fenster_start"],
            "ende": basis["fenster_ende"],
        },
        "kalibrierung": {
            "calibration_ref": basis.get("calibration_ref"),
            "calibration_status": basis.get("calibration_status"),
        },
        "systemgrenze": basis["systemgrenze"],
        "workload_einheit": basis.get("workload_einheit"),
        "verglichen_am": _jetzt_utc(),
    }


def _self_check() -> int:
    """Strukturpruefung ohne Datenfiktion: Gates und Fehlerpfade."""
    with __import__("tempfile").TemporaryDirectory() as tmp:
        pfad = str(pathlib.Path(tmp) / "register.jsonl")
        zeilen = [
            {"timestamp": "2026-11-20T%02d:00:00+01:00" % stunde, "value": float(10 + stunde),
             "source_type": "direct_sensor"}
            for stunde in range(6)
        ]
        ergebnis = register_baseline(
            pfad, "selfcheck_leistung", "kW", True, zeilen,
            "selfcheck:pumpe-01", min_samples=3,
        )
        assert ergebnis["status"] == BASELINE_REGISTRIERT, ergebnis
        nachher = [
            {"timestamp": "2026-11-25T%02d:00:00+01:00" % stunde, "value": float(stunde),
             "source_type": "direct_sensor"}
            for stunde in range(6)
        ]
        vergleich = vergleiche_gegen_baseline(
            pfad, "selfcheck_leistung", nachher, "selfcheck:pumpe-01",
            min_samples=3,
        )
        assert vergleich["status"] == "VALID", vergleich
        abweichend = vergleiche_gegen_baseline(
            pfad, "selfcheck_leistung", nachher, "andere-grenze", min_samples=3,
        )
        assert abweichend["status"] == NICHT_VERGLEICHBAR, abweichend
        zu_wenig = register_baseline(
            pfad, "sel_kurz", "kW", True, zeilen[:1], "selfcheck:pumpe-01",
            min_samples=3,
        )
        assert zu_wenig["status"] == NICHT_REGISTRIERT, zu_wenig
        assert len(_lade_eintraege(pfad)) == 1, "NICHT_REGISTRIERT darf nichts anhaengen"
    print(json.dumps({"mechanismus": "getestet", "reale_messreihe": "NICHT_GEPRUEFT"},
                     sort_keys=True, ensure_ascii=True))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Baseline-Register je Kennzahl (Vorher-Nachher, REUSE impact.py)"
    )
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--register", metavar="REGISTER_JSONL")
    parser.add_argument("--vergleiche", metavar="REGISTER_JSONL")
    parser.add_argument("--kennzahl")
    parser.add_argument("--unit")
    parser.add_argument("--systemgrenze")
    parser.add_argument("--workload-einheit")
    parser.add_argument("--calibration-ref")
    parser.add_argument(
        "--calibration-status", choices=list(CALIBRATION_STATUSSE)
    )
    parser.add_argument("--richtung", choices=["hoeher_schlechter", "hoeher_besser"],
                        default="hoeher_schlechter")
    parser.add_argument("--csv", help="Messreihe (timestamp,value,source_type)")
    parser.add_argument("--min-samples", type=int)
    parser.add_argument("--dqi-min", type=float)
    parser.add_argument("--noise-factor", type=float)
    args = parser.parse_args(argv)

    def _csv_rows() -> List[Dict[str, Any]]:
        if not args.csv:
            parser.error("--csv is required for --register/--vergleiche")
        return load_csv(args.csv)  # REUSE

    try:
        if args.self_check:
            return _self_check()
        if args.register:
            ergebnis = register_baseline(
                args.register,
                args.kennzahl or "",
                args.unit or "",
                args.richtung == "hoeher_schlechter",
                _csv_rows(),
                args.systemgrenze or "",
                workload_einheit=args.workload_einheit,
                calibration_ref=args.calibration_ref,
                calibration_status=args.calibration_status,
                min_samples=args.min_samples,
                dqi_min=args.dqi_min,
                noise_factor=args.noise_factor,
            )
        elif args.vergleiche:
            ergebnis = vergleiche_gegen_baseline(
                args.vergleiche,
                args.kennzahl or "",
                _csv_rows(),
                args.systemgrenze or "",
                workload_einheit=args.workload_einheit,
                min_samples=args.min_samples,
                dqi_min=args.dqi_min,
                noise_factor=args.noise_factor,
            )
        else:
            parser.error("choose --self-check, --register or --vergleiche")
            return 2
    except (BaselineRegisterError, ValueError) as fehler:
        print(json.dumps({"fehler": str(fehler)}, ensure_ascii=True))
        return 2
    print(json.dumps(ergebnis, sort_keys=True, ensure_ascii=True))
    if ergebnis["status"] in (BASELINE_REGISTRIERT, "VALID", "NO_IMPROVEMENT"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

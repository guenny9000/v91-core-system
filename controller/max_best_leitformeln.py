"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
MAX-BEST-Leitformeln: ausfuehrbares Modell der vier Leitformeln aus
docs/V91-FORMELN.md (Kanonisches Formeldokument, #547/#550).

NEU und verbindlich ist NICHT die Formel (die steht im Kanon), sondern
die Maschinenpruefbarkeit: W_t, G_t, B_(n+1) und Q_repo existieren hier
als reine Funktionen. Die Pruefdisziplin wird REUSE aus
controller/max_best_rechner.py uebernommen (KEINE zweite
Validierungslogik, KEINE zweite Wahrheit): Unknown-Propagation als
NICHT_GEPRUEFT (dargestellt als None), fail-closed Domains
(KEIN stilles Clampen), Strukturverletzungen als MaxBestInputError.

Domains laut Kanon (DOMAIN != MEINUNG):
- W_t = alpha*A_t + beta*M_t + gamma*D_t - delta*S_t
  mit alpha, beta, gamma > 0, delta > 0, A/M/D/S >= 0.
- G_t = (1 + lambda*Dankbarkeit_t)/(1 + kappa*Uebermut_t) * Demut_t
  mit lambda, kappa > 0, Dankbarkeit in [0,1], Demut in (0,1],
  Uebermut >= 0. Nenner ist stets >= 1, KEIN Unendlich moeglich.
- B_(n+1) = B_n + eta_n * (O_real - B_n)
  mit eta_n in (0,1], B_n >= 0, O_real >= 0.
- Q_repo = Sum(I_geprueft) / (1 + Sum(R_unnoetig) + Sum(F_ungeprueft))
  mit Zaehlungen I, R, F >= 0 (Anzahl, keine Prozentwerte).

Ehrliche Grenzen (verbindlich):
- FORMEL != MESSUNG: alle Eingaben sind ANGABEN; dieses Modul misst
  NICHTS selbst (EINGABE == ANGABE != BEWEIS).
- KEIN Menschenmass: W_t bewertet BEITRAEGE und Handlungen, NIEMALS
  den Wert eines Menschen (KEINE_PERSONENBEWERTUNG).
- RECHNEN != ENTSCHEIDEN: Ausgaben sind Zahlen, keine Beschluesse,
  keine Autorisierungen (ZAHLEN_BINDEN_NICHT unveraendert).
- RECHNER != AGENT: kein Netz, kein Daemon, kein Zugriff auf fremde
  Systeme.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

REUSE_KERN = "controller/max_best_rechner.py"  # alleinverbindlich fuer Kern-/Leitformeln-Disziplin
from controller import max_best_rechner as kern  # REUSE: Validierung + Fehlerstand + Berichtform

NICHT_GEPRUEFT = kern.NICHT_GEPRUEFT
MaxBestInputError = kern.MaxBestInputError


def _zahl(value: Any, name: str, minimum: float = 0.0,
          maximum: float | None = None,
          echt_positiv: bool = False,
          echt_groesser_null: bool = False) -> float | None:
    """REUSE der Kern-Validierung plus strikte Zusatzdom,

    echt_positiv: Wert muss > 0 sein (z.B. Parameter).
    echt_groesser_null: Wert muss > 0 und <= maximum sein (Demut, eta).
    Beides fail-closed; UNKNOWN propagiert weiterhin als None.
    """
    number = kern._as_float(value, name, minimum=minimum, maximum=maximum)
    if number is None:
        return None
    if echt_positiv and number <= 0.0:
        raise MaxBestInputError("%s muss echt positiv sein, ist %r" % (name, value))
    if echt_groesser_null:
        if number <= 0.0:
            raise MaxBestInputError("%s muss echt groesser 0 sein, ist %r" % (name, value))
    return number


def _bericht(name: str, value: float | None) -> dict[str, Any]:
    result = kern._result(value)
    result["formel"] = name
    return result


def mitwirkung_w(alpha: Any, beta: Any, gamma: Any, delta: Any,
                 aktiv: Any, kooperation: Any, demut: Any,
                 schaden: Any) -> dict[str, Any]:
    """W_t = alpha*A + beta*M + gamma*D - delta*S (Kanon: Mitwirkung)."""
    a = _zahl(alpha, "alpha", echt_positiv=True)
    b = _zahl(beta, "beta", echt_positiv=True)
    g = _zahl(gamma, "gamma", echt_positiv=True)
    d = _zahl(delta, "delta", echt_positiv=True)
    A = _zahl(aktiv, "aktiv")
    M = _zahl(kooperation, "kooperation")
    D = _zahl(demut, "demut")
    S = _zahl(schaden, "schaden")
    if any(v is None for v in (a, b, g, d, A, M, D, S)):
        return _bericht("W_t = alpha*A + beta*M + gamma*D - delta*S", None)
    wert = a * A + b * M + g * D - d * S
    return _bericht("W_t = alpha*A + beta*M + gamma*D - delta*S", wert)


def stabilitaet_g(lam: Any, kappa: Any, dankbarkeit: Any,
                  demut: Any, uebermut: Any) -> dict[str, Any]:
    """G_t = (1 + lambda*Dankbarkeit)/(1 + kappa*Uebermut) * Demut."""
    l = _zahl(lam, "lambda", echt_positiv=True)
    k = _zahl(kappa, "kappa", echt_positiv=True)
    dank = _zahl(dankbarkeit, "dankbarkeit", minimum=0.0, maximum=1.0)
    dem = _zahl(demut, "demut", minimum=0.0, maximum=1.0, echt_groesser_null=True)
    ueb = _zahl(uebermut, "uebermut", minimum=0.0)
    if any(v is None for v in (l, k, dank, dem, ueb)):
        return _bericht("G_t = (1 + lambda*Dankbarkeit)/(1 + kappa*Uebermut) * Demut", None)
    wert = (1.0 + l * dank) / (1.0 + k * ueb) * dem
    return _bericht("G_t = (1 + lambda*Dankbarkeit)/(1 + kappa*Uebermut) * Demut", wert)


def verbesserung_schritt(b_n: Any, eta: Any, o_real: Any) -> dict[str, Any]:
    """B_(n+1) = B_n + eta * (O_real - B_n) (Kanon: Verbesserung)."""
    bn = _zahl(b_n, "b_n")
    et = _zahl(eta, "eta", minimum=0.0, maximum=1.0, echt_groesser_null=True)
    o = _zahl(o_real, "o_real")
    if bn is None or et is None or o is None:
        return _bericht("B_(n+1) = B_n + eta_n*(O_real - B_n)", None)
    wert = bn + et * (o - bn)
    return _bericht("B_(n+1) = B_n + eta_n*(O_real - B_n)", wert)


def bestandspflege_q(i_geprueft: Any, r_unnoetig: Any,
                     f_ungeprueft: Any) -> dict[str, Any]:
    """Q_repo = I / (1 + R + F) (Kanon: Bestandspflege, Zaehlungen)."""
    i = _zahl(i_geprueft, "i_geprueft")
    r = _zahl(r_unnoetig, "r_unnoetig")
    f = _zahl(f_ungeprueft, "f_ungeprueft")
    if i is None or r is None or f is None:
        return _bericht("Q_repo = Sum(I_geprueft)/(1 + Sum(R_unnoetig) + Sum(F_ungeprueft))", None)
    wert = i / (1.0 + r + f)
    return _bericht("Q_repo = Sum(I_geprueft)/(1 + Sum(R_unnoetig) + Sum(F_ungeprueft))", wert)


BEREICHE = ("mitwirkung", "stabilitaet", "verbesserung", "bestandspflege")


def berechne(auftrag: Any) -> dict[str, Any]:
    """Berechnet die Leitformeln aus EINEM strukturierten Auftrag.

    Auftragsform (alle Bereiche optional, UNKNOWN erlaubt):
    {"mitwirkung": {"alpha":..., "beta":..., "gamma":..., "delta":...,
                    "aktiv":..., "kooperation":..., "demut":..., "schaden":...},
     "stabilitaet": {"lambda":..., "kappa":..., "dankbarkeit":...,
                     "demut":..., "uebermut":...},
     "verbesserung": {"b_n":..., "eta":..., "o_real":...},
     "bestandspflege": {"i_geprueft":..., "r_unnoetig":..., "f_ungeprueft":...}}
    """
    if not isinstance(auftrag, dict):
        raise MaxBestInputError("Auftrag muss ein JSON-Objekt sein")
    for key in auftrag:
        if key not in BEREICHE:
            raise MaxBestInputError("unbekannter Leitformel-Bereich: %r" % key)
        if not isinstance(auftrag[key], dict):
            raise MaxBestInputError("%s muss ein Objekt sein" % key)
    report: dict[str, Any] = {}
    if "mitwirkung" in auftrag:
        t = auftrag["mitwirkung"]
        report["mitwirkung"] = mitwirkung_w(
            t.get("alpha"), t.get("beta"), t.get("gamma"), t.get("delta"),
            t.get("aktiv"), t.get("kooperation"), t.get("demut"),
            t.get("schaden"))
    if "stabilitaet" in auftrag:
        t = auftrag["stabilitaet"]
        report["stabilitaet"] = stabilitaet_g(
            t.get("lambda"), t.get("kappa"), t.get("dankbarkeit"),
            t.get("demut"), t.get("uebermut"))
    if "verbesserung" in auftrag:
        t = auftrag["verbesserung"]
        report["verbesserung"] = verbesserung_schritt(
            t.get("b_n"), t.get("eta"), t.get("o_real"))
    if "bestandspflege" in auftrag:
        t = auftrag["bestandspflege"]
        report["bestandspflege"] = bestandspflege_q(
            t.get("i_geprueft"), t.get("r_unnoetig"), t.get("f_ungeprueft"))
    nicht_geprueft = sum(1 for v in report.values()
                         if v["status"] == NICHT_GEPRUEFT)
    report["bilanz"] = {"formeln": len(report),
                        "nicht_geprueft": nicht_geprueft}
    report["grenzen"] = {
        "formel != messung": True,
        "rechnen != entscheiden": True,
        "keine_personenbewertung": True,
        "eingaben": "ANGABE != BEWEIS",
        "reuse_disziplin": REUSE_KERN,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MAX-BEST-Leitformeln (W_t, G_t, B_n, Q_repo) "
                    "maschinenpruefbar; FORMEL != MESSUNG; "
                    "RECHNEN != ENTSCHEIDEN")
    parser.add_argument("eingabe", nargs="?", default="-",
                        help="JSON-Datei oder - fuer stdin")
    args = parser.parse_args(argv)
    try:
        if args.eingabe == "-":
            text = sys.stdin.read()
        else:
            text = pathlib.Path(args.eingabe).read_text(encoding="utf-8")
        auftrag = json.loads(text)
        report = berechne(auftrag)
    except (OSError, json.JSONDecodeError, MaxBestInputError) as exc:
        print("MAX-BEST-LEITFORMELN FEHLER (fail-closed): " + str(exc))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # exit 0: alles berechenbar; 1: mind. ein NICHT_GEPRUEFT (ehrlich
    # sichtbar, KEIN Scheitern); 2: Struktur-/Lesefehler.
    return 0 if report["bilanz"]["nicht_geprueft"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

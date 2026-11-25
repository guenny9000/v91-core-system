# doku-pinnende Tests fuer docs/V91-FORMELN.md (VIBE-LXXXCLXXXV)
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-FORMELN.md"
RAW = DOC.read_text(encoding="ascii")
T = re.sub(r"\s+", " ", RAW)  # umbruch-normalisiert fuer Phrasen-Asserts


def test_formel_w():  assert "W_t = alpha * A_t + beta * M_t + gamma * D_t - delta * S_t" in T
def test_formel_g():  assert "G_t = (1 + lambda * Dankbarkeit_t) / (1 + kappa * Uebermut_t) * Demut_t" in T
def test_formel_b():  assert "B_(n+1) = B_n + eta_n * (O_real - B_n)" in T
def test_formel_q():  assert "Q_repo = Sum(I_geprueft) / (1 + Sum(R_unnoetig) + Sum(F_ungeprueft))" in T


def test_domainen():
    assert "alpha > 0" in T and "delta > 0" in T
    assert "Dankbarkeit_t in [0,1]" in T
    assert "Demut_t in (0,1]" in T
    assert "Uebermut_t >= 0" in T
    assert "eta_n in (0,1]" in T


def test_kein_messanspruch():
    assert "FORMELN == LEITBILD != MESSUNG" in T
    assert "EINGABE/ANGABE" in T
    assert "ANGABE != BEWEIS" in T


def test_negativsonde_kein_zweiter_rechner():
    assert "Es gibt KEINEN zweiten Rechner" in T
    assert "max_best_rechner" in T
    assert "ALLEINVERBINDLICH" in T
    assert "von KEINEM Modul automatisch ausgewertet" in T
    for verbot in ("Modul rechnet W_t", "W_t wird automatisch berechnet",
                   "Formeln werden von Modul X implementiert"):
        assert verbot not in T


def test_negativsonde_keine_implementationsbehauptung():
    assert "implementierte Auswertung ist aktiv" not in T
    assert "Messwerte liegen vor" not in T


def test_verweis_ziele_existieren():
    root = DOC.parents[1]
    assert (root / "controller" / "max_best_rechner.py").exists()
    assert any(root.glob("tests/test_max_best*.py"))


def test_ascii_pure():
    RAW.encode("ascii")


def test_grenze_size():
    assert len(RAW.encode()) < 8192

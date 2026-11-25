"""Konsolidierung FORMELN-Duplikat (#548-Wurzel -> kanonisch, 25.11.2026):

sichert, dass (a) die Wurzeldatei NUR noch Verweis ist und KEINE
Formelinhalte doppelt (NO_DUPLICATE), (b) die kanonische Datei die
eingaengigen Formeln UND die uebernommenen Abschnitte traegt,
(c) nur die kanonische Datei die Alleinverbindlichkeit behauptet.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KANON = ROOT / "docs" / "V91-FORMELN.md"
STUB = ROOT / "FORMELN.md"
K = re.sub(r"\s+", " ", KANON.read_text(encoding="ascii"))
S = re.sub(r"\s+", " ", STUB.read_text(encoding="ascii"))


def test_stub_ist_nur_verweis():
    assert "VERWEISDATEI" in S
    assert "docs/V91-FORMELN.md" in S


def test_stub_hat_keine_formeln():
    for formel in ("W_t =", "G_t =", "B_(n+1)", "P(a) =", "E =", "argmax"):
        assert formel not in S, "Formelduplikat: " + formel


def test_kanon_hat_uebernommene_abschnitte():
    for satz in ("P(a) = H_ohne - H_mit(a) - C(a) - R(a)",
                 "E = N_nuetzlich / R_eingesetzt",
                 "KEINE Division durch null",
                 "KEIN_NACHFITTEN",
                 "ZAHLEN_BINDEN_NICHT",
                 "argmax W(x)"):
        assert satz in K, "fehlt im Kanon: " + satz


def test_alleinverbindlichkeit_nur_im_kanon():
    assert "ALLEINVERBINDLICHE Formelreferenz" in K
    # der Stub verweist NUR, er ist nicht selbst Verbindlich
    assert "NUR noch ein" in S


def test_beide_ascii_pure():
    KANON.read_text(encoding="ascii")
    STUB.read_text(encoding="ascii")

"""
Konsolidierung Dauerprotokoll-Duplikat (#543/#544, 25.11.2026):

sichert, dass (a) die Parallel-Datei NUR noch Verweis ist und KEIN
Protokollinhalt doppelt (NO_DUPLICATE), (b) der Kanon die
verlustfrei uebernommenen VORLAGE-Abschnitte traegt, die NUR in
der #543-Datei standen, (c) Kanon und Stub ASCII-pure bleiben und
der Kanon kompakt (< 8 KiB) bleibt, (d) die Provenienz im Stub
erhalten bleibt (ISOLATE_NOT_DESTROY).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KANON = ROOT / "docs" / "V91-MAX-BEST-DAUERPROTOKOLL.md"
STUB = ROOT / "docs" / "V91-MAX-BEST-DAUERPROTOKOLL-RESSOURCEN-LEBENSCHUTZ.md"
K = re.sub(r"\s+", " ", KANON.read_text(encoding="ascii"))
S = re.sub(r"\s+", " ", STUB.read_text(encoding="ascii"))


def test_stub_ist_nur_verweis():
    assert "VERWEIS" in S
    assert "docs/V91-MAX-BEST-DAUERPROTOKOLL.md" in S
    assert "NUR" in S


def test_stub_hat_keine_protokollinhalte():
    for phrase in ("Oberstes Ziel",
                   "Abschalt- und Isolierungsprinzip",
                   "dauerhaft reduzieren",
                   "NICHT GEPRUEFT - keine blinde Abschaltung",
                   "Endgueltige Prioritaetenordnung",
                   "Leitsatz (VORLAGE-Wortlaut)",
                   "Ressourcenverschwendung ->"):
        assert phrase not in S, "Protokollinhalt gedoppelt: " + phrase


def test_kanon_hat_verlustfreie_deltas():
    for satz in ("Keine Abschaltung aufgrund bloszer Vermutungen",
                 "Nicht behauptet: weltweite Server oder Kraftwerke abgeschaltet zu haben",
                 "Eine solche globale Steuerungsmoeglichkeit besteht hier nicht",
                 "1. Menschenleben und Menschenwuerde.",
                 "2. Nahrung, Wasser, Medizin und Grundversorgung.",
                 "7. Nachhaltiger Fortschritt fuer alle.",
                 "Nicht blind zerstoeren, sondern Verschwendung beenden",
                 "Erhalten, was Leben ermoeglicht, und verbessern, was allen nuetzt"):
        assert satz in K, "fehlt im Kanon: " + satz


def test_kanon_kompakt_unter_8kib():
    assert KANON.stat().st_size < 8 * 1024


def test_beide_ascii_pure():
    KANON.read_text(encoding="ascii")
    STUB.read_text(encoding="ascii")


def test_provenienz_erhalten():
    assert "PR #543" in S
    assert "PR #544" in S
    assert "ISOLATE_NOT_DESTROY" in S

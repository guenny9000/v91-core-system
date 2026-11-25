"""
RealRun-Zykluscheck (25.11.2026, Betreiber-Fremd-Entwurf aufgenommen):

sichert, dass (a) der 4-Fragen-Abschlussblock GRENZE/VERSCHWENDUNG/
BELEG/UEBERGABE vollstaendig gepinnt ist, (b) keine Grundsaetze aus dem
bestehenden Kanon gedoppelt werden (NO_DUPLICATE, Negativ-Sonden), (c)
das Dokument ASCII-pure und < 8 KiB bleibt, (d) die Verweisobjekte und
den Leitsatz traegt, (e) BILANZ != ENTSCHEIDUNG verriegelt ist.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md"
D = re.sub(r"\s+", " ", DOC.read_text(encoding="ascii"))


def test_vier_fragen_vollstaendig():
    for frage in ("1. GRENZE:", "2. VERSCHWENDUNG:", "3. BELEG:", "4. UEBERGABE:"):
        assert frage in D, "fehlt: " + frage


def test_vier_fragen_inhalte():
    assert "nicht geprueft oder nicht gemessen" in D
    assert "NICHT GEPRUEFT markiert" in D
    assert "Doppelarbeit" in D
    assert "Ressourcenverschwendung" in D
    assert "Messwert, Testlauf, Artefakt" in D
    assert "ohne Reibung direkt weiterfuehren" in D


def test_leitsatz_gepinnt():
    assert "jeden Zyklus ein kleines Stueck" in D
    assert "besser verlassen als man ihn vorgefunden hat" in D
    assert "nachweislich bessere reale Welt" in D


def test_kein_kanon_duplikat_negativsonden():
    for phrase in ("AUTARKIE FOERDERN",
                   "MENSCHENLEBEN SCHUETZEN",
                   "Mit Demut lernen",
                   "Endgueltige Prioritaetenordnung",
                   "Oberstes Ziel",
                   "deterministic cycle",
                   "REUSE vor Neubau"):
        assert phrase not in D, "Kanon-Duplikat: " + phrase


def test_verweise_auf_kanon_existieren():
    for ziel in ("V91-MAX-BEST-GELUEBNIS.md",
                 "V91-MAX-BEST-PROTOCOL.md",
                 "V91-MAX-BEST-ENTDECKUNGSAUFTRAG.md",
                 "V91-MAX-BEST-ZUSAMMENARBEIT.md"):
        assert "docs/" + ziel in D, "Verweis fehlt: " + ziel
        assert (ROOT / "docs" / ziel).exists(), "Datei fehlt: " + ziel


def test_bilanz_nicht_entscheidung_verriegelt():
    assert "BILANZ != ENTSCHEIDUNG" in D
    assert "FREIGABE != BERECHTIGUNG" in D
    assert "UNKNOWN" in D


def test_ascii_pure_und_kompakt():
    DOC.read_text(encoding="ascii")
    assert DOC.stat().st_size < 8 * 1024


def test_provenienz_erhalten():
    assert "FREMD-ENTWURF" in D
    assert "NO_DUPLICATE_SYSTEMS" in D

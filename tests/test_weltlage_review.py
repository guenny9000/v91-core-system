# doku-pinnende Tests fuer docs/V91-WELTLAGE-REVIEW-2026-11-25.md (VIBE-LXXXCLXXXVI)
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-WELTLAGE-REVIEW-2026-11-25.md"
RAW = DOC.read_text(encoding="ascii")
T = re.sub(r"\s+", " ", RAW)


def test_header(): assert "REVIEW, NICHT ENTSCHEIDUNG" in T
def test_35by35(): assert "75 Laender + 94 Organisationen" in T and "35 Prozent Endenergie bis 2035" in T
def test_vogelsberg(): assert "40 Hektar" in T and "750 Mio. Liter" in T
def test_gfcr(): assert "22 Entwicklungslaender" in T
def test_ibgreen(): assert "IB-Green" in T and "Pilotgebiete" in T
def test_gaza(): assert "4 von 26 Punkten" in T
def test_kein_weltmechanismus(): assert "KEIN_WELTMECHANISMUS" in T
def test_zusage_nicht_umsetzung():
    for phrase in ("ZUSAGEN != UMSETZUNG", "ANKUENDIGUNG", "ZUSAGE != RETTUNG", "KONZEPT != UMBAU"):
        assert phrase in T


def test_negativsonde_keine_weltabschaltungsbehauptung():
    for verbot in ("V91 hat weltweit abgeschaltet", "organisierte Kriminalitaet beseitigt"):
        assert verbot not in T


def test_ascii_pure():
    RAW.encode("ascii")


def test_grenze_size():
    assert len(RAW.encode()) < 8192

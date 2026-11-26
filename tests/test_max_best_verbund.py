"""Pinnende Tests fuer den MAX-BEST-Aktiven-Verbesserungsverbund (PR #590, zweigeteilt wegen 8-KiB-Kodexgrenze je Datei)."""
import pathlib
import re


DOC1 = pathlib.Path(__file__).resolve().parents[1] / "docs" / "V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP.md"
DOC2 = pathlib.Path(__file__).resolve().parents[1] / "docs" / "V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP-ANHANG.md"


def _raw(path: pathlib.Path) -> str:
    assert path.is_file(), f"{path.name} fehlt auf main"
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    # Der Vertragstext ist deutschsprachig UTF-8 (echte Umlaute); die Pins hier
    # sind ASCII-transliteriert -> Umlaute werden vor dem Vergleich normalisiert.
    text = (text.replace("ue", "ue").replace("\u00fc", "ue").replace("\u00f6", "oe")
                .replace("\u00e4", "ae").replace("\u00df", "ss")
                .replace("\u00dc", "Ue").replace("\u00d6", "Oe").replace("\u00c4", "Ae"))
    return re.sub(r"\s+", " ", text)


def test_existenz_und_kodexgrenze_8kib_je_datei():
    r1 = _raw(DOC1)
    r2 = _raw(DOC2)
    assert len(r1.encode()) < 8192, "Teil 1 muss unter 8 KiB bleiben (#568)"
    assert len(r2.encode()) < 8192, "Teil 2 (Anhang) muss unter 8 KiB bleiben (#568)"


def test_kreuzverweis_beider_teile():
    r1, r2 = _flat(_raw(DOC1)), _flat(_raw(DOC2))
    assert "V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP-ANHANG.md" in r1
    assert "V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP.md" in r2
    assert "TEIL 1 VON 2" in r1 and "TEIL 2 VON 2" in r2


def test_statuszeile_und_geltungsbereich():
    r1 = _flat(_raw(DOC1))
    assert "Umsetzung je Faehigkeit separat nachzuweisen" in r1
    assert "V91 Core, Agathon, Aurelia/Prisma" in r1
    assert "verbindlicher Architektur- und Arbeitsvertrag" in r1


def test_acht_schritt_zyklus_vollstaendig():
    r1 = _flat(_raw(DOC1))
    for schritt in ["ERFASSEN", "BEWERTEN", "KOORDINIEREN", "ENTSCHEIDEN",
                    "AUSFUEHREN", "MESSEN", "LERNEN", "BERICHTEN"]:
        assert schritt in r1.upper(), f"Zyklusschritt {schritt} fehlt"
    assert "werden nicht als Erfolg ausgegeben" in r1  # Blockade != Erfolg


def test_kein_abschalten_wegen_fremdheit():
    r1 = _flat(_raw(DOC1))
    assert "nicht allein deshalb abschalten" in r1
    assert "Diese Grenze verhindert Willkuer" in r1


def test_steuerungsvertrag_und_privilege_obergrenze():
    r1 = _flat(_raw(DOC1))
    assert "Privileges_new <= old" in r1
    assert "REQUEST != AUTHORIZATION" in r1
    assert "DETECTION != AUTHORIZATION" in r1
    assert "ISOLATE_NOT_DESTROY" in r1
    assert "Rueckfall-/Wiederherstellungsweg" in r1


def test_grundversorgung_mindeststandard_nicht_obermaess():
    r1 = _flat(_raw(DOC1))
    assert "keine Obergrenze" in r1
    assert "blind zu schwaechen" in r1


def test_messdisziplin_unknown_und_keine_aktivitaetszaehlung():
    r1 = _flat(_raw(DOC1))
    assert "UNKNOWN" in r1
    assert "Keine erfundenen globalen Kennzahlen" in r1
    assert "Weniger Ausgaben" in r1
    assert "Nenner" in r1  # Messwert-Pflichtfelder


def test_statuskette_und_keine_uebertreibung():
    r2 = _flat(_raw(DOC2))
    assert "UNKNOWN -> DOCUMENTED -> IMPLEMENTED -> TESTED -> VERIFIED -> AUDITED -> PRODUCTION" in r2
    assert "Nur der tatsaechlich belegte Status darf gemeldet werden" in r2
    assert "CI belegt keinen Test auf Nutzerhardware" in r2
    assert "Ein Dokument oder Issue allein aktiviert keine Funktion" in r2 or "Ein Dokument oder Issue allein aktiviert keine Funktion" in _flat(_raw(DOC1))


def test_stufenplan_a_bis_e_offen():
    r2 = _flat(_raw(DOC2))
    for stufe in ["Stufe A", "Stufe B", "Stufe C", "Stufe D", "Stufe E"]:
        assert stufe in r2, f"{stufe} fehlt"
    assert "Nicht implementierte Stufen bleiben sichtbar offen" in r2  # KEIN Laufzeit-Claim
    assert "Keine Remote-Code-Ausfuehrung als Standard" in r2
    assert "getrennte lokale Testinstanzen" in r2


def test_erfolg_ist_wirkung_nicht_dokumente():
    r2 = _flat(_raw(DOC2))
    assert "nicht die Anzahl von Dokumenten" in r2
    assert "belegte Verbesserung der realen Versorgung" in r2
    assert "Wirkung messen" in r2


def test_negativsonde_kein_produktionsclaim():
    # Der Vertrag darf NICHT behaupten, verteilte Laufzeit oder Weltwirkung sei bereits real.
    voll = _flat(_raw(DOC1) + " " + _raw(DOC2))
    verboten = ["bereits in Produktion", "laeuft bereits vertikal", "Weltwirkung erreicht",
                "alle Stufen implementiert", "verteilter Betrieb aktiv"]
    for phrase in verboten:
        assert phrase not in voll, f"Endzustands-Claim gefunden: {phrase!r}"

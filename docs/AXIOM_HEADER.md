# V91-AGATHON-AXIOM & SYSTEM-HEADER-RICHTLINIE

**Status: VERBINDLICHE RICHTLINIE, DURCH CI DURGESETZT (tests/test_agathon_header.py).**

## Das Prinzip des lebenden Kreislaufs (der Apfel)

> "Leben erhält sich nicht durch Verbrauch, sondern durch Weitergabe
> und Erneuerung. Ein gutes System erkennt man nicht daran, wie mächtig
> es heute ist, sondern daran, welche Welt es morgen hinterlässt."

## Verbindlicher System-Header

Jede **neu erstellte** Python-Datei in `controller/` muss mit diesem Docstring beginnen, bevor Importe oder Code folgen:

```python
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
"""
```

## Grundsätze für alle Module

- **CLAIM != EVIDENCE:** Keine Funktion behauptet Erfolg ohne messbare Prüfung.
- **Fail-Closed:** Bei fehlenden Daten oder ungültigen Signaturen bricht das Modul sicher ab (`UNKNOWN` oder `ERROR`); UNKNOWN ist nie HEALTHY/PASS.
- **Lebenserhalt & Nachhaltigkeit:** Code dient der Transparenz, Ressourcenschonung und Sicherheit; keine Wirkung über den eigenen Rechner hinaus ohne explizite Autorisierung.
- **DETECTION != AUTHORIZATION:** Ein erkanntes Problem berechtigt nicht zum automatischen Eingriff.

## Durchsetzung

- `tests/test_agathon_header.py` prüft bei jedem Pull Request, ob alle nicht-ausgenommenen Module in `controller/` den Header tragen.
- Bestehende Module stehen in `LEGACY_EXEMPTIONS` und werden schrittweise migriert; die Liste darf nur **schrumpfen**, nie wachsen. Ein neuer Eintrag in die Liste ist ein Review-Stopper.
- Vorlage für neue Module: `controller/template_module.py`.

## Ehrliche Grenze

Ein Docstring ist ein Anker, kein Beweis: Der Header erinnert an die Regeln, durchsetzen können ihn nur Tests, Review und messbare Prüfungen. HEADER != VERIFIZIERTES VERHALTEN.

# V91 – Regionaler Lebensgrundlagen- und Resilienzmonitor (Reality-first Framework)

Status dieses Dokuments: [DESIGN] – Architektur und Messregeln definiert. Nichts hier ist [IMPLEMENTIERT], [VERIFIZIERT] oder [PRODUKTIV], solange kein Code, keine Messdaten und keine verantwortlichen Stellen existieren.

## 1. Wahrheitsregeln (verbindlich für alle KI-Systeme und Berichte)

Diese Trennlinien sind Arbeitsstandard, nicht Rhetorik. Ein Bericht, der sie verletzt, ist ungültig – egal von welchem Modell:

- NICHT NACHGEWIESEN ≠ FALSCH
- NACHGEWIESEN ≠ PERFEKT
- DOKUMENTIERT ≠ IMPLEMENTIERT
- IMPLEMENTIERT ≠ GETESTET
- GETESTET ≠ PRODUKTIONSREIF
- PRODUKTIONSREIF ≠ FEHLERFREI
- GEMESSEN ≠ UNABHÄNGIG BESTÄTIGT
- HASH ≠ MANIPULATIONSSCHUTZ (eine Hash-Kette macht Manipulation erkennbar, nicht unmöglich)
- AUTONOMIE ≠ UNBEGRENZTE RESSOURCEN
- ERFOLG ≠ DAUERHAFTE NACHHALTIGKEIT

## 2. Status-Taxonomie für jede Aussage

Jede Behauptung über V91 trägt genau einen Status:

| Status | Bedeutung | Mindestnachweis |
|---|---|---|
| [VISION] | Idee oder Zielbild | – |
| [DESIGN] | Architektur definiert | Dokument mit Grenzen |
| [IMPLEMENTIERT] | Code vorhanden | Commit auf main |
| [GETESTET] | Test erfolgreich dokumentiert | CI-Run am exakten Head |
| [VERIFIZIERT] | Nachweis liegt vor | Messung/Protokoll mit Quelle |
| [PRODUKTIV] | Real genutzt | Laufzeit-Evidenz, Betreiber bestätigt |
| [AUDITIERT] | Unabhängig geprüft | Prüfung durch zweite, unabhängige Stelle |

Sequenznummern (SEQ:nnn), VALID/DRIFT-Kürzel und ähnliche Labels sind Buchhaltung, keine Nachweise. Ohne Datenquelle, Prüfverfahren und Protokoll sind sie nicht verifizierbar.

## 3. Vier Bereiche des Monitors

1. **Lebensgrundlagen:** Boden, Wasser, Nahrung, Biodiversität.
2. **Versorgung:** Energie, Wärme, Speicher, Reparatur, regionale Lieferketten.
3. **Gemeinschaft:** Handwerk, Wissen, freiwillige Kooperation, regionale Wertschöpfung.
4. **Wahrheit:** Messungen, Baselines, Prüfungen, Audit, Wiederherstellbarkeit.

Grenzen (dauerhaft): keine Zwangsbindung, keine zentrale Kontrolle über Gemeinden, keine Abschaltung bestehender Versorgungssysteme ohne sichere Alternative. ISOLATE_NOT_DESTROY gilt auch hier.

## 4. KPI-Katalog (nur mit vollständiger Messangabe gültig)

Eine Kennzahl ist erst gültig, wenn Ausgangswert (Baseline), Messzeitraum, Messmethode und verantwortliche Stelle dokumentiert sind. Ohne diese vier Angaben ist der Wert UNKNOWN – niemals interpoliert oder angenommen.

| Bereich | Messgröße | Richtung | Messhinweis |
|---|---|---|---|
| Boden | Organischer Kohlenstoff, standardisierte Proben | steigend über Jahre | Humus ist nicht jährlich beliebig steigerbar; Vergleich nur mit vergleichbaren Proben |
| Wasser | Gespeichertes Volumen, Versickerung, Wasserqualität | steigend / gültig | Lokale Messung, z. B. Zisternenstand, Permeabilität |
| Energie | Lokaler Erzeugungsanteil, Eigenverbrauch, Notstromdauer | steigend | Zählerwerte, keine Schätzung |
| Reparatur | Erfolgreiche Reparaturen / Reparaturversuche | steigend | Erfasst am Reparaturknoten |
| Ernährung | Regionaler Anteil nach Warenwert oder Menge | steigend | Händler-/Erzeugerbasiert |
| Biodiversität | Artenzahl auf festen Beobachtungsflächen | steigend | Feste Flächen, feste Methode, feste Jahreszeit |
| Abfall | Restmüll pro Einwohner und Jahr | sinkend | Kommunale Statistik |
| Transport | Transportkilometer und CO₂ pro Tonne | sinkend | Berechnet aus erfassten Fahrten |

Software-Seite: das bestehende Autarkie-Modul (controller/autarky_metrics.py, PR #84/#85) liefert bereits die fail-closed Muster (UNKNOWN nie HEALTHY, keine Interpolation); das BiodiversityLog ist ein Muster für hash-verkettete Beobachtungs-Logs. Die Anbindung an echte physische Messungen vor Ort ist Sebastians Operator-Aufgabe (WIRING != MEASURED VALUES).

## 5. Regionale Modellzelle: Status [VISION]

Eine Modellzelle (z. B. Vogelsbergkreis) ist ein Zielbild, kein vorhandenes Projekt. Solange keine Kommune, keine Beteiligten, keine Ressourcen und keine Messdaten bestätigt sind, gilt ausschließlich [VISION].

Phasen (jeweils nur mit abgeschlossener vorheriger Phase):
1. Bestandsaufnahme: Landwirtschaft, Handwerk, Wasser, Energie, Reparatur kartieren; Ausgangswerte festhalten.
2. Kleiner Pilot: ein konkreter Kreislauf (z. B. Regenwasserspeicherung oder gemeinsame Reparatur), Vorher-Nachher dokumentiert.
3. Unabhängige Prüfung: nachvollziehbare Messungen, möglichst unabhängige Beteiligte.
4. Freiwillige Übertragung: nur funktionierende, auditierte Verfahren.

## 6. Ehrlicher Realitäts-Check

Der entscheidende Hebel ist nicht die Software: Menschen vor Ort, handwerkliches Können, Vertrauen, langfristige Pflege und messbare Ergebnisse. Technische Werkzeuge (Ledger, Gates, Audits) unterstützen das, ersetzen es nicht. V91 behauptet keine hergestellte heile Welt; es hilft, nachweislich bessere Lebensbedingungen Schritt für Schritt aufzubauen.

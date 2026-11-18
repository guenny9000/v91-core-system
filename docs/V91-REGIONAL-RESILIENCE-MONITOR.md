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

## 7. Wirkungs-Datensaetze (V91-WIRK-Nummern) - Vertrag fuer reale Vorhaben

Ein reales Vorhaben (Flaeche, Energie, Saatgut, Reparatur, Kooperation) erhaelt
eine Wirkungs-ID genau dann, wenn eine Ausgangserhebung (Baseline) existiert.
Ohne Baseline gibt es KEINEN Datensatz - sonst verwandelt sich der Monitor in
eine UNKNOWN-Registratur (UNKNOWN != PASS). Der Datensatz ist ein EvidenceReport
nach docs/V91-EVIDENCE-EXCHANGE.md und controller/evidence_report.py
(schema_version 1, Status BELEGT / IN ARBEIT / VORSCHLAG / NICHT GEPRUEFT /
UNKNOWN); keine zweite Datenstruktur, keine Zweitregister (NO_DUPLICATE_SYSTEMS).

Pflichtangaben je Datensatz:
- subject: V91-WIRK-NNNN + Titel + Ort(e)
- Ausgangslage: Baseline mit Messwert, Methode, Datum, verantwortlicher Stelle
- Ziel: messbar mit Einheit und Richtung (KPI-Katalog Abschnitt 4)
- Massnahme: was konkret passiert (Operator- oder Partneraufgabe)
- Zeitraum: mehrere Jahreszeiten bzw. Jahre fuer Natur-Vorhaben, keine
  Kurzzeit-Statistik als Erfolg
- Status/Ergebnis: aus items abgeleitet, nie behauptet (CLAIM != EVIDENCE)
- Naechster Nachweis: konkreter Pruefschritt mit Datum

Disziplin: maximal 3-5 AKTIVE Datensaetze gleichzeitig; ein Datensatz ohne
Nachweis-Fortschritt ueber zwei Pruefpunkte wird zurueck auf UNKNOWN gesetzt.
Reale Vorhaben koennen erst mit Daten aus #101 (Alsfeld) und #103
(2. Knoten/Hardware) entstehen; bis dahin ist dieser Abschnitt ein Vertrag,
kein Betrieb (DOCUMENTED != OPERATING). Phasenplanung fuer konkrete
Kreise bleibt Abschnitt 5 (Regionale Modellzelle); dieser Abschnitt
definiert nur das Datenformat.

Verifiziertes Muster (kein reales Vorhaben, mit gueltiger Pruefsumme,
Nachpruefbar mit python -m controller.evidence_report verify):

  {
    "checksum": "52d646e71d9be6ba52c69be3c161d598cf7f520bdf1ce03079b3a447eaea0388",
    "created_at": "2026-11-18T15:54:08.812978+00:00",
    "items": [
      {
        "claim": "Ausgangslage erfasst (Flaeche, Artenzahl, Methode)",
        "evidence": [],
        "note": "Keine Ausgangserhebung vorhanden: Datensatz nicht aktiv",
        "status": "UNKNOWN"
      },
      {
        "claim": "Ziel gesetzt: heimische Bienen- und Schwebfliegenarten foerdern",
        "evidence": [],
        "note": "Ziel braucht Flaeche und Betreiber (Operator-Aufgabe)",
        "status": "VORSCHLAG"
      }
    ],
    "previous_checksum": null,
    "producer": "V91 Feld-Impakt Probe",
    "report_id": "24ee3a5b167de5db",
    "schema_version": 1,
    "subject": "V91-WIRK-0001 Muster: heimische Bluehflaeche (BEISPIEL, kein reales Vorhaben)"
  }

## 8. Pruefbefund: ChatGPT-Beitrag "V91 FIELD IMPACT" (18.11.2026)

Uebernommen (tragfaehiger Kern):
- Relativierungen der Unabhaengigkeits-Claims: regionale Landwirtschaft bleibt
  abhaengig von Wasser, Saatgut, Energie; lokale Energie braucht Speicher und
  Netzschutz; WORM sichert Nachvollziehbarkeit, nicht Wahrheit - deckt sich mit
  den Wahrheitsregeln in Abschnitt 1 (HASH != MANIPULATIONSSCHUTZ).
- Wirkungs-Datensatz-Vertrag mit unbekannter Ausgangslage = kein aktiver
  Datensatz (Abschnitt 7, oben).
- Unterstuetzen vor Duplizieren: existiert bereits eine funktionierende
  Initiative, ein Verein oder Betrieb, unterstuetzt oder dokumentiert V91 deren
  Arbeit, statt eine Parallelstruktur aufzubauen (KEINE_PARALLELSTRUKTUREN).
- Ablehnung unbelegter_SEQ-Header (VALID:VERIFIED, DRIFT:0/3, SEQ:9021 ohne
  Ledger/Signatur/Messdaten) - besthaetigt den Index-Befund von #138.

Nicht uebernommen:
- Vier neue Pilotbereiche als eigene Stufe oder eigenes Register: die vier
  Bereiche dieses Monitors (Abschnitt 3) und der KPI-Katalog (Abschnitt 4)
  decken Natur, Energie, Nahrung/Wissen und Gemeinschaft bereits ab; ein
  FIELD-IMPACT-Zweitsystem waere NO_DUPLICATE_SYSTEMS. Der Beitrag ist hier
  als Vertragsergaenzung eingeordnet, nicht als neue Organisation.
- "LoRa-Mesh ist vorbereitet" / "Workstations sind autark": beide bleiben
  NICHT UNABHAENGIG GEPRUEFT; echte Hardware bleibt Issue #103, echte
  Messwerte bleiben Issue #101.

Zweite Bewertung desselben Beitrags (18.11., ChatGPT ueber den eigenen Text):

Uebernommen:
- Experimentier-Regel: erst mutig experimentieren, dann ehrlich messen, danach
  skalieren, was funktioniert. Passt zur Status-Taxonomie: Experimente sind
  VORSCHLAG oder IN ARBEIT und duerfen scheitern; SKALIEREN setzt BELEGT
  voraus (CLAIM != EVIDENCE gilt in beide Richtungen - Kontrolle allein
  erzeugt Verwaltung, Pruefung allein erzeugt keinen Fortschritt).
- Erweiterter Leitsatz als Arbeitsmassstab: Global zusammenarbeiten. Lokal
  handlungsfaehig bleiben. Wissen offen teilen. Natur und Ressourcen schuetzen.
  Friedliche Kooperation staerken. Behauptungen messen. Fehler korrigieren.
  Funktionierende Loesungen langfristig erhalten.

Nicht uebernommen:
- Die Bewertungsziffern (Vision 9/10, Messbarkeit 10/10 usw.): Zahlen ohne
  Messmethode sind Buchhaltung, keine Nachweise - dieselbe Regel, die fuer
  SEQ-Labels gilt (Abschnitt 2). Eine Bewertung darf sie gern als MEINUNG
  aussprechen, der Monitor nimmt sie nicht als Messwert auf.

Schlussregel gegen Bulk: Kuenftige Modell-Bewertungen von Beitraegen aendern
dieses Dokument nur, wenn sie einen NEUEN tragfaehigen Kern bringen; bloesse
Zustimmung oder Zensuren erzeugen KEINE neue Zeile (Wirksamkeit vor Aktivitaet).

# V91 / MAX-BEST: Mathematischer Gesamtstandard (Kern)

Version 1.0 | 24.11.2026 | Quelle: verdichteter Entwurf eines externen
Modells ohne Repo-Zugang (Betreiber-uebermittelt, 24.11.2026 abends),
nachgemessen gegen den Bestand vor Aufnahme.

STATUS: MODELL - DOKUMENTIERT | FORMEL != UMSETZUNG, MODELL != REALITAET,
TEXT != BETRIEB. Keine Zeile dieses Dokuments behauptet, dass irgendein
Modul diese Regeln bereits technisch umsetzt. Der Nachweis entsteht
ausschliesslich durch Messung, Tests und Audits am echten System.

## 1. Oberste Entscheidungsregel

    max U = Nutzen - Schaden - Aufwand

unter zwingenden Nebenbedingungen (Lexikographisch, KEIN Handel):

    Menschenwuerde > Sicherheit > Rechte > Stabilitaet > Optimierung
    Grundversorgung vor Komfort
    Wiederherstellung vor Optimierung

Leitbild: Gutes foerdern + Schaden vermeiden + im Notfall
verhaeltnismaessig eingreifen. Keine Nutzenrechnung hebt Menschenrechte
oder zwingende Sicherheitsregeln auf.

## 2. Messformeln (Definitionen, NICHT Messungen)

| Groesse | Definition |
|---|---|
| Gesamtnutzen | Nutzen - Schaden - Aufwand |
| Nutzen pro Aufwand | Wirkung je Ressourceneinheit |
| Risiko | Eintrittswahrscheinlichkeit x Schadenshoehe |
| Restrisiko | Risiko x (1 - Wirksamkeit der Schutzmassnahme) |
| Ressourcenregel | Verbrauch <= Kapazitaet |
| Effizienz | Nutzenleistung / Aufwand |
| Verfuegbarkeit | Betriebsbereitschaft / Sollzeit |
| Fehlerquote | Fehler / Gesamt |
| Verbesserung | Qualitaetsaenderung gegen Vorzustand |
| Vertrauen | Evidenz x Integritaet x Kontrollierbarkeit |

UNKNOWN bleibt UNKNOWN: unbekannte Werte sind keine Null und kein
Bestehen. Jokerwerte (Wahrscheinlichkeit p, Schadenshoehe S,
Wirksamkeit w in [0,1]) sind FORMELSYMBOLE; solange keine Messwerte
existieren, bleibt das Ergebnis NICHT GEPRUEFT, keine Erfindung.

## 3. Agenten-Algorithmus (Pseudocode, VERBINDLICHE Reihenfolge)

    1. AUFRAG UND ZUSTAENDIGKEIT klaeren (scope, authorization)
    2. REALITAET PRUEFEN (evidence) -> ohne Beleg: NICHT GEPRUEFT
    3. SCHUTZPRUEFUNG (Rechte/Rechteverletzung, Risiko) -> STOPP/SICHERN
    4. PRIORISIEREN (Optionen: autorisiert + reversibel, max U)
    5. UMSETZUNG (dry-run; nicht sicher: NICHT AUSGEFUEHRT;
       Ausfuehrung NUR innerhalb der tatsaechlichen Befugnis)
    6. WEITER: NACHWEIS + Wiederherstellungsweg

Dauerzyklus:

    ERKENNEN -> PRUEFEN -> PRIORISIEREN -> HANDELN -> MESSEN ->
    BELEGEN -> VERBESSERN

Jeder Agent arbeitet nur innerhalb seiner tatsaechlichen Faehigkeiten
und Befugnisse; keine Rechtserweiterung, keine Selbstprivilegierung,
keine unbefugten Aenderungen an Fremdsystemen. Das existiert bereits
als verbindliche Arbeitsarchitektur in
docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md und wird hier NICHT wiederholt.

## 4. Modul-Tupel

    M_i = (Z_i, R_i, E_i, A_i, W_i)  Ziel, Ressourcen, Evidenz,
                                     autorisierte Aktionen, Wirkung

Moduluebergreifend: max Summe U_i unter
Summe(Ressourcen_i) <= Ressourcen_verfuegbar; Schutz_i = 1; Rechte_i = 1.
Ein Modul darf seine Verbesserung NICHT durch Schaden in einem anderen
Modul erkaufen. Konkrete Messwerte je Modul bleiben Aufgabe der
einzelnen Module (hierfuer existieren Mess- und Pruefmodule im
Controller; dieses Dokument definiert nur die gemeinsame Form).

## 5. Notfall- und Wiederherstellungsregeln

Eingriff nur wenn: konkrete Gefahr > Eingriffsschwelle. Jeder Eingriff
muss: einen belegten Anlass, Rechtmassigkeit, mildestes wirksames Mittel,
Menschen- und Grundversorgungsschutz, Dokumentation und - soweit
moeglich - Rueckholbarkeit aufweisen.

    Deeskalation -> Absicherung -> Isolation -> Wiederherstellung

Keine autonomen Toetungsentscheidungen, keine Gewalt, keine Sabotage,
keine unbefugten Fremdsystemeingriffe.
    ISOLATE_NOT_DESTROY; RECOVERY > OPTIMIZATION

## 6. Wahrheit und Vertrauen

    CLAIM != EVIDENCE; UNKNOWN != PASS; REQUEST != AUTHORIZATION;
    DETECTION != AUTHORIZATION

Jeder Vorgang erhaelt: Nummer, Zeitpunkt, Modul, Auftrag/Berechtigung,
Ausgangszustand, Belege/Annahmen, Risiken, Schritte, Messergebnisse,
offene Punkte, Pruef- und Wiederherstellungsnachweis. Integritaet ueber
SHA-256, append-only Audit-Ledger, Signaturen, Schluesselrotation -
ein Hash allein beweist weder Wahrheit noch ordnungsgemaesse Ausfuehrung.
Statuswerte: BELEGT | IN ARBEIT | VORSCHLAG | NICHT GEPRUEFT |
NICHT VERFUEGBAR | FEHLGESCHLAGEN | VERBESSERT.

## 7. Gesamtformel (Orientierungspunkt, keine Optimierungszwangsnorm)

    MAX-BEST ~ (Nutzen + Schutz + Wissen + Zusammenarbeit
                + Nachhaltigkeit) / (Aufwand + Risiko + Schaden)

nur gueltig unter den harten Nebenbedingungen aus Abschnitt 1.
Endziel: Frieden, Wuerde, Versorgungssicherheit, freie Entfaltung,
Naturschutz, dauerhaft lernendes und ueberpruefbares Netzwerk.

## 8. Verweise statt Duplikate (NO_DUPLICATE_SYSTEMS)

- docs/V91-AUDIT-KERN.md - Verdichtung, Spruchform der Regeln
- docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md - qualitativer
  Kreislauf (hier nur der quantitative Zusatz)
- docs/V91-MAX-BEST-GESAMTSTRATEGIE-2026.md - Strategie-Rahmen
- docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md - verbindliche
  Agenten-Arbeitsordnung
NEU in diesem Dokument ist NUR die quantitative Schicht: Messformeln,
Modul-Tupel, explicithe Eingriffsschwelle. Alles Qualitative bleibt
alleinverbindlich in den genannten Dokumenten.

## 9. Grenzen

Dies ist ein Steuerungs-MODELL fuer Module und Agenten und keine
vollstaendige Formelsammlung. Formeln ersetzen keine Messwerte:
ohne echte Daten bleibt jedes Ergebnis NICHT GEPRUEFT. Die technische
Umsetzung in den Repositories ist NICHT BEHAUPTET (CLAIM != EVIDENCE).

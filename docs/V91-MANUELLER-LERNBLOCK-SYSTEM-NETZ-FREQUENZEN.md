# V91 – Manueller Lernblock: System, Netz, Geometrie und Frequenzen

**Version:** 0.1 · **Datum:** 15.11.2026  
**Zweck:** Verständlicher Lern- und Prüfpfad für den Aufbau eines friedlichen, dezentralen, menschenwürdigen und nachweisbaren Resilienzsystems.

> Dieser Lernblock beschreibt Ziele, Begriffe und Prüfverfahren. Er behauptet weder einen vollständigen Ausbau noch Produktivbetrieb. Jede Fähigkeit erhält erst dann den Status IMPLEMENTIERT oder VERIFIZIERT, wenn Code, Tests und konkrete Belege vorliegen.

## 1. Das Grundbild

V91 lässt sich in fünf Ebenen denken:

1. **Knoten:** einzelne Geräte oder Dienste mit eigener Identität, begrenzten Ressourcen und eigener Verantwortung.
2. **Verbindungen:** erlaubte, authentisierte Kommunikationswege zwischen Knoten.
3. **Daten:** Messwerte, Aufgaben, Ergebnisse und Nachweise mit Herkunft, Zeit und Einheit.
4. **Regeln:** Grenzen, Berechtigungen, Sicherheitsprüfungen und menschliche Freigaben.
5. **Wirkung:** ein messbarer Nutzen, etwa weniger Energieverbrauch, bessere Verfügbarkeit oder schnellere Wiederherstellung.

Ein Netz ist nicht automatisch dezentral, nur weil viele Geräte beteiligt sind. Entscheidend ist, ob einzelne Knoten ausfallen oder sich abmelden können, ohne dass das ganze System unkontrollierbar wird.

## 2. Die wichtigsten Sicherheitsregeln

- REQUEST ist keine AUTHORIZATION.
- DETECTION ist keine AUTHORIZATION.
- CLAIM ist kein EVIDENCE.
- UNKNOWN ist kein PASS.
- ISOLATE_NOT_DESTROY.
- Schutz von Menschen und Grundversorgung steht über Stabilität, Zustimmung, Nachhaltigkeit und Neuerung.
- Keine Gewalt, keine Zwangsübernahme, keine Sabotage und keine Gefährdung lebenswichtiger Infrastruktur.
- Jede externe Wirkung braucht passende Berechtigung, Begrenzung, Protokollierung und Rückweg.

## 3. Geometrie: Wie ist das Netz aufgebaut?

Ein Netz kann als Graph beschrieben werden:

- Knoten (N): Geräte oder Dienste.
- Kanten (E): bestätigte Verbindungen zwischen zwei Knoten.
- Pfad: eine Folge von Verbindungen von einem Start- zu einem Zielknoten.
- Komponente: eine Gruppe von Knoten, die untereinander verbunden ist.
- Schnittstelle: der definierte Übergang zu einem anderen System.

### Kleine Beispielrechnung

Angenommen, es gibt vier freiwillig teilnehmende Knoten A, B, C und D. Die Verbindungen sind A–B, B–C und C–D.

- Anzahl Knoten: N = 4
- Anzahl Verbindungen: E = 3
- Mittlerer Grad: 2E/N = 6/4 = 1,5
- Link-Dichte eines ungerichteten Graphen: 2E/[N(N−1)] = 6/12 = 0,5
- Komponenten: 1

Das ist nur ein Rechenbeispiel, keine Messung eines realen V91-Netzes.

### Was bedeuten die Geometrie-KPIs?

- **Knotenzahl:** Wie viele berechtigte Knoten sind aktuell aktiv?
- **Link-Dichte:** Wie dicht ist das Netz verbunden?
- **Mittlerer Grad:** Wie viele direkte Verbindungen hat ein Knoten durchschnittlich?
- **Komponentenzahl:** In wie viele getrennte Gruppen ist das Netz zerfallen?
- **Pfadredundanz:** Gibt es alternative Wege, wenn eine Verbindung ausfällt?
- **Zentralisierung:** Hängt zu viel Verkehr oder Arbeit an einem einzigen Knoten?
- **Wiederverbindungszeit:** Wie lange dauert es nach einer kontrollierten Trennung, bis erlaubte Verbindungen wieder funktionieren?

Mehr Verbindungen sind nicht immer besser. Ein kompromittierter Knoten muss sicher isoliert werden können. Datenschutz und Zustimmung begrenzen, welche Topologiedaten gesammelt werden dürfen.

## 4. Frequenzen: Was wird tatsächlich gemessen?

Das Wort Frequenz braucht immer einen Bezug:

- **Abtastfrequenz:** Wie oft misst ein Sensor pro Sekunde? Einheit Hertz (Hz).
- **Netzfrequenz:** Frequenz eines Stromnetzes, in Europa typischerweise 50 Hz. Für Sicherheitsentscheidungen zählt ein geeignetes Messgerät, nicht eine unkalibrierte Software-Schätzung.
- **Funksignal:** Trägerfrequenz und belegte Bandbreite. Messungen nur mit geeigneter und rechtlich zulässiger Empfangstechnik.
- **Taktabweichung:** Unterschied einer lokalen Uhr zu einer festgelegten Zeitquelle, z. B. in Millisekunden oder ppm.
- **Netzwerk-Taktung:** Abtast- oder Aktualisierungsintervall eines Dienstes.
- **KI-Durchsatz:** Tokens pro Sekunde; das ist eine Rate, keine Funkfrequenz.

V91 darf keine Funkfrequenzen belegen, keine fremden Netze verändern und keine Kommunikation stören. Empfangsmessung ist von Aussendung zu unterscheiden. Jede Aussendung oder aktive Funkprüfung benötigt gesonderte rechtliche Grundlage und Freigabe.

## 5. KPI: Vom Begriff zum Beweis

Jeder KPI braucht fünf Angaben:

1. Was wird gemessen?
2. In welcher Einheit?
3. Aus welcher Quelle stammt der Wert?
4. Über welchen Zeitraum wurde gemessen?
5. Wie groß ist die Unsicherheit?

Beispiel: „CPU-Auslastung 40 %“ ist unvollständig. Besser: „CPU-Auslastung 40 %, Host-Messquelle X, 60-Sekunden-Mittelwert, Messzeit 12:00 UTC, Collector-Version Y, Commit Z.“

### Kern-KPIs

| Bereich | KPI | Einheit |
|---|---|---|
| Betrieb | Verfügbarkeit | % |
| Geschwindigkeit | P95-Latenz | ms |
| Fehler | Fehlerrate | % |
| Aufgaben | Alter ältester Auftrag | Sekunden |
| Ressourcen | CPU/RAM/GPU-Auslastung | % oder MiB |
| Energie | Energie pro erledigter Aufgabe | Wh/Aufgabe |
| Netzwerk | Durchsatz / Jitter / Paketverlust | bit/s / ms / % |
| Geometrie | Knotenzahl / Link-Dichte / Pfadredundanz | Anzahl / Verhältnis |
| Zeit | Uhrabweichung | ms oder ppm |
| Wiederherstellung | RTO / RPO | Minuten |
| Beweisqualität | Vollständigkeit der Herkunftsdaten | % |

Es gibt keine echten KPI-Werte ohne Messdaten. Fehlende Werte bleiben UNKNOWN. Schätzungen müssen ausdrücklich als ESTIMATED gekennzeichnet sein.

## 6. Die Systembausteine

Ein vollständiges Zielsystem benötigt mindestens:

- Identität und Authentisierung jedes Knotens.
- Rollen und eng begrenzte Berechtigungen.
- Sichere lokale Messwerterfassung.
- Einheitliches Daten- und KPI-Schema.
- Aufgabenwarteschlange mit eindeutigen Auftrags-IDs.
- Ressourcenbegrenzung für CPU, RAM, GPU, Speicher und Netzwerk.
- Integritätsgeschütztes Audit-Log.
- Signierte Updates und überprüfbare Herkunft.
- Sicherung, Wiederherstellung und Rollback.
- Freiwillige Peer-Verbindungen mit gegenseitiger Authentisierung.
- Datenschutz, Aufbewahrung und Datenexport.
- Alarmierung und nachvollziehbare menschliche Freigabe.
- Regelmäßige Tests für Ausfall, Trennung, beschädigte Daten und Wiederherstellung.

Die README-Komponentenmatrix hält fest, welche Bausteine im Repository bereits teilweise vorhanden, nur dokumentiert oder noch nicht implementiert sind.

## 7. Lern- und Ausbaufolge

1. **Verstehen:** README und Architektur lesen; Begriffe und Statuswerte erklären können.
2. **Beobachten:** lokale Daten ausschließlich lesend erfassen.
3. **Messen:** Quellen, Einheiten, Zeitstempel und Qualität ergänzen.
4. **Rechnen:** KPI-Formeln mit festen Testdaten prüfen.
5. **Absichern:** Authentisierung, Berechtigungen und Fehlerfälle testen.
6. **Wiederherstellen:** Backup und Restore in einer Testumgebung durchführen.
7. **Verbinden:** zwei eigene Testknoten freiwillig und authentisiert koppeln.
8. **Belasten:** nur isolierte Testumgebungen kontrolliert auf Ausfall prüfen.
9. **Bewerten:** Nutzen, Kosten, Energie, Wasser, Risiken und Verteilungsgerechtigkeit vergleichen.
10. **Freigeben:** Produktivbetrieb erst nach unabhängiger Prüfung und gesonderter Freigabe.

## 8. Manuelles Lernprotokoll

Für jeden Lernschritt wird eine Zeile geführt:

- Datum und Uhrzeit:
- Thema:
- Ausgangsstand / Commit:
- Erwartung:
- Ausgeführte Handlung:
- Messquelle und Einheit:
- Ergebnis:
- Test / Beleg:
- Status: BELEGT / IMPLEMENTIERT / VERIFIZIERT / UNKNOWN / FEHLGESCHLAGEN
- Risiko:
- Rückweg:
- Nächster kleinster sicherer Schritt:

## 9. Erste praktische Übung

**Aufgabe:** Vier Knoten und drei Verbindungen als Papiermodell zeichnen und die Geometrie-KPIs aus Abschnitt 3 berechnen.

**Erfolgskriterium:** Jede Zahl lässt sich aus N und E nachvollziehen. Es wird nicht behauptet, dass diese Knoten real existieren.

**Nächster Schritt:** Erst wenn das Modell verstanden ist, ein kleines lokales JSON-Testfixture mit Knoten- und Kantenliste anlegen und die Formeln automatisiert testen.

## 10. Was „volle Wirkung“ sachlich bedeutet

Volle Wirkung ist kein Schalter und keine Behauptung über das gesamte Internet, alle Systeme oder Frequenzen. Sie entsteht schrittweise durch:

- konkrete Probleme und betroffene Menschen verstehen;
- freiwillige und rechtmäßige Zusammenarbeit;
- messbare Verbesserung gegenüber einer dokumentierten Ausgangslage;
- Schutz vor Nebenwirkungen und ungleicher Verteilung;
- offene, reparierbare und portable Technik;
- unabhängige Überprüfung und Wiederherstellbarkeit.

**Leitsatz:** Erst messen, dann verstehen, dann begrenzt verbessern, danach unabhängig prüfen. Keine globale Wirkung behaupten, die nicht belegt ist.

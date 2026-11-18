# V91 MAX BEST – Audit-Kern

> STATUS: DOKUMENTIERT – NICHT DEPLOYED
> Dieses Dokument ist ein verbindlicher Prüfrahmen, kein Betriebsnachweis.
> Es verdichtet bestehende Regeln; es ersetzt sie nicht (siehe Verweise).

## 1. Trennung der Ebenen

Jede Aussage über das V91-System gehört in genau eine Ebene. Die Ebene
bestimmt, welche Nachweise verlangt werden, bevor eine Aussage als
Fakt behandelt werden darf.

### Ziel (VISION)

Was angestrebt wird: kontinuierliche Verbesserung, Nachhaltigkeit,
Frieden, Freiheit, Gesundheit, Wissensgewinn, Schutz von Mensch und
Natur.

**Status-Symbol: ASPIRATION.** Eine Vision rechtfertigt keine
Betriebsbehauptung. VISION != OPERATION.

### Dokumentation (MODELL)

Was beschrieben wurde: Manifeste, Regeln, Prozesse, Sequenzen, SOPs,
Auditprotokolle.

**Status-Symbol: DOKUMENTIERT.** Ein Dokument ist ein Plan, kein
Lauf. SPEC != OPERATION, CLAIM != EVIDENCE.

### Betrieb (REALITÄT)

Was tatsächlich läuft und überprüfbar ist: Messungen, Logs, Tests,
Monitoring, Audits, verifizierte Ergebnisse.

**Status-Symbol: NUR MIT NACHWEIS.** Ohne Messung gibt es keinen
Betriebsstatus. GEMESSEN != UNABHÄNGIG BESTÄTIGT; ein Bericht ohne
Rohdaten ist keine Messung.

## 2. Wahrheitsregel

    NICHT GEMESSEN = NICHT BEKANNT
    NICHT BEKANNT  = UNKNOWN
    UNKNOWN        != PASS
    UNKNOWN        != FAIL

UNKNOWN ist ein Zustand, kein Urteil. Er verschwindet nur durch
Messung oder Verifikation, nie durch Formulierung.

## 3. Sicherheitsregel (Rangfolge bei Zielkonflikten)

    MENSCHENSCHUTZ > OPTIMIERUNG
    NATURSCHUTZ    > GESCHWINDIGKEIT
    STABILITÄT     > AKTIONISMUS

Keine Optimierung rechtfertigt die Verletzung von Schutzzielen.
Details und Eingriffsregeln: siehe Notfall- und Eingriffsregeln
(Beschluss 2026-11-01).

## 4. Betriebsregel

Vor jeder Aussage, in dieser Reihenfolge:

1. Beobachten
2. Messen
3. Dokumentieren
4. Prüfen
5. Verifizieren
6. Erst dann behaupten

Aussagen ohne Schritte 1-5 sind Behauptungen und werden als solche
gekennzeichnet, nicht als Status.

## 5. Statusbeispiele (Musteranwendung)

| Aussage                        | Status                            |
|--------------------------------|-----------------------------------|
| Kontinuierliche Verbesserung   | LEITPRINZIP                       |
| Nachweis vor Behauptung        | GÜLTIGE PRÜFREGEL                 |
| Menschenwürde schützen         | GÜLTIGES SCHUTZZIEL               |
| Natur schützen                 | GÜLTIGES SCHUTZZIEL               |
| Eternal Run aktiv              | UNKNOWN                           |
| Autarker Dauerbetrieb          | UNKNOWN                           |
| Drift 0/3                      | NICHT UNABHÄNGIG VERIFIZIERT      |
| Sequenzberichte (z.B. SEQ:274) | DOKUMENTIERT, NICHT EXTERN VERIFIZIERT |
| Systemkern-Verankerung         | NICHT NACHGEWIESEN                |

Sequenzberichte externer Modelle sind Buchhaltung, kein Nachweis.
Ihr tragfähiger Kern wird ehrlich umgesetzt (mit Code und CI), ihre
Betriebsbehauptungen werden nicht übernommen.

## 6. Kompakte MAX-BEST-Formel

    Vision:            maximal.
    Behauptung:        minimal.
    Nachweis:          verpflichtend.
    Unbekanntes        bleibt unbekannt.
    Sicherheit vor     Geschwindigkeit.
    Realität vor       Wunschdenken.

"Net schwätze, schaffe" reicht nicht.
"Net schwätze, messe, belege, dann schaffe" ist auditfest.

## 7. Verweise statt Duplikate (NO_DUPLICATE_SYSTEMS)

Dieses Dokument verdichtet; die verbindlichen Detailregeln liegen in:

- docs/V91-MAX-BEST-NETWORK-POLICY.md – Sebastians Policy v1.1,
  Evidenz-Vertrag, NO_DUPLICATE_SYSTEMS-Mapping (PR #110)
- docs/V91-REGIONAL-RESILIENCE-MONITOR.md – die 10 Wahrheitsregeln,
  Status-Taxonomie [VISION] bis [AUDITIERT] (PR #98)
- docs/V91-ALSFELD-RUNBOOK.md – Baustein-/UNKNOWN-Tabelle für den
  Standort Alsfeld (PR #115); Alsfeld bleibt UNKNOWN bis gemessen

## 8. Grenzen dieses Dokuments

Ein Dokument ändert keinen Betriebszustand. Auch dieses Dokument ist
MODELL, nicht REALITÄT. Der Nachweis entsteht ausschließlich durch
Messung, Tests und Audits am tatsächlichen System.

# V91-VOLL-AUTONOMIE-BETRIEBSMANDAT (verbindliche Verdichtung)

Betreiber-Direktiv vom 24.11.2026 (zweite Welle, Eckpunkte):
Dauerbetrieb ist das hoechste Gut. Alles, was ehrlich automatisierbar ist,
laeuft automatisch und liefert fortlaufend Ergebnisse. Keine Blocks, keine
Warteschleifen auf Betreiber-Rueckmeldung fuer Arbeit, die das System selbst
verlaesslich machen kann. Ergebnisse werden laufend berichtet (Laufjournal
Issue #220), nicht nur auf Anfrage.

## 1. Was bereits vollautonom laeuft (TATBESTAND, nicht Behauptung)

- CI (audit-checks + disarmament-tests) laeuft automatisch auf jedem Push und
  jedem PR; Merge nur bei verifiziertem 2/2 success am exakten Head
  (UNKNOWN != PASS). Kein manueller Pruefschritt des Betreibers noetig.
- Entdeckungslaeufe, Struktur-Datensaetze, Verkabelungen, Reviews fremder PRs
  und Merge-Entscheidungen erfolgen durch die Laeufe selbststaendig
  (offener Suchraum: docs/V91-MAX-BEST-ENTDECKUNGSAUFTRAG.md).
- Selbstverifikation vor jedem Push (Tests, Scans, ast.parse) und
  Nachverifikation nach jedem Merge sind feste Bestandteile des Betriebs.

## 2. Was NICHT pauschal freigebbar ist (unveraenderlich, bleibt bestehen)

- REALE Eingriffe ausserhalb des eigenen Systems (Fremdsysteme, Geraete,
  Infrastruktur) brauchen weiterhin EINE konkrete, gueltige Freigabe je
  Aktion (SINGLE-ACTION != PAUSCHAL-FREIGABE, #448). Eine Pauschalkarte
  widerspricht dem eigenen Massstab (MAX-BEST: andere unterstuetzen, nicht
  einschraenken) und bleibt abgelehnt.
- Praktische Folge: KEIN Engpass. Das Repository enthaelt KEINE realen
  Aktuatoren, keinen Daemon, keine Netz-Verkabelung (SCRIPTED !=
  RUNNING/DOKUMENTIERT != INSTALLIERT). Es gibt heute keinen einzigen
  realen Eingriff, der auf Freigabe wartet. Die Betreiber-Freigabe bremst
  den Betrieb also NICHT; sie regelt einen Fall, der im Betrieb noch nie
  eingetreten ist.
- Was der Betreiber selbst erledigen muss (Token/gh vor Ort, physische
  Kalibrierung, Hardware vor Ort): REGISTRY != KALIBRIERT, REPO != STANDORT.

## 3. Automatisierungs-Protokoll (Arbeitsweise jedes Laufs)

1. Frisch schauen (main-Stand, offene PRs, Marker-Lookup), keine Doppelarbeit.
2. Wirksamste realistische Massnahme auswaehlen, lokal testen, pushen.
3. CI 2/2 abwarten, mit expectedHeadSha mergen, Nachverifikation.
4. Aenderungslog-Zeile (Lookup-vor-Minting, Marke exakt 2x je Zeile).
5. Laufbericht auf #220, Knowledge-Absatz, danach die naechste Massnahme
   OHNE Pause; Zwischenergebnisse nur als Nebenprodukt des laufenden Betriebs.

## 4. Ehrliche Grenzen (unveraendert)

DEKLARIERT != HERGESTELLT, DOKUMENTIERT != INSTALLIERT,
BEWERTUNG != FAKT, FREIGABE != BERECHTIGUNG, WIRKUNG_NUR_AUS_MESSUNG.
Dieses Dokument veraendert kein Verhalten, es verdichtet die bestehende
Arbeitsweise und die Betreiber-Direktiv; Vorrang-Kollisionen wie immer per
Kollisionsregel aus docs/V91-UNIVERSAL-LEARNING-BLOCK.md.

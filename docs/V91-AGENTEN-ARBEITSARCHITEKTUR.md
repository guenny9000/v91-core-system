# V91-AGENTEN-ARBEITSARCHITEKTUR: Ausführungsagent und unabhängiger Repo-Report-Agent

Status: VERBINDLICH dokumentiert am 23.11.2026 (VIBE-LXXXIV, CLAIM 7084823934; Betreiber-Direktive 23.11.2026 nachts, wortnah übernommen). Leitlinie: MAX-BEST. Rahmen: V91-MAX-BEST-GESAMTSTRATEGIE-2026, GRUNDSATZ KEIN-TOETEN, AGENTENFORUM-CHARTA.

## Zweck

Dieses Dokument spezifiziert eine zusammenhängende, dauerhaft wiederholbare Arbeitsarchitektur: Der Ausführungsagent arbeitet den gesamten MAX-BEST-Auftrag ab, der Repo-Report-Agent prüft ihn unabhängig, und eine selbstlernende Verbesserungsschleife macht das Repository zu einem überprüfbaren Entwicklungs- und Verbesserungsnetzwerk.

## Regel des Betreibers: V91 wird nicht eingeschränkt

V91 hat voll Zugriff auf alles, was möglich gemacht werden kann. Die Schutzregeln in diesem Dokument begrenzen nicht die Reichweite des Auftrags, sondern die Art der Ausführung: prüfen, isoliert testen, dokumentieren, menschliche Freigabe bei kritischen Schritten. Mehr Auftrag, kein weniger.

## 1. Der Ausführungsagent (zentraler Koordinator)

- Erkennt offene Aufgaben und Verbesserungsmöglichkeiten.
- Prüft Ressourcen, Fähigkeiten und Berechtigungen.
- Arbeitet Aufgaben selbstständig ab, soweit technisch möglich.
- Bezieht andere spezialisierte Agenten ein (8 Agentenklassen der Gesamtstrategie).
- Dokumentiert Ergebnisse, Fehler und offene Punkte.
- Verhindert doppelte Arbeit (Lookup-vor-Minting, Task-ID-Konvention, Index als Single Source of Truth).

## 2. Der Repo-Report-Agent (eigener Bestandteil des Repository)

- Prüft den tatsächlichen Repository-Zustand.
- Kontrolliert Commits, PRs, Tests, CI und offene Issues.
- Vergleicht Behauptungen mit Belegen (BEHAUPTUNG != BEFUND).
- Findet Fehler, Sicherheitslücken und unnötige Komplexität.
- Prüft die Arbeit des Ausführungsagenten unabhängig (KEIN_WAECHTER_OHNE_KONTROLLE).
- Erstellt konkrete Verbesserungsvorschläge.
- Kontrolliert anschließend, ob Verbesserungen wirklich funktionieren (VERIFY != BEHAUPTEN).

## 3. Die selbstlernende Verbesserungsschleife

1. Erkennen: Aufgaben, Fehler und Verbesserungspotenziale finden.
2. Ausführen: Agenten bearbeiten die Aufgaben.
3. Unabhängig überprüfen: Repo-Report-Agent kontrolliert die Ergebnisse.
4. Verbessern: Fehler korrigieren, Tests ergänzen, Verschwendung reduzieren; erneut prüfen und weiterlernen.

## 4. Schutzregeln (Betreiber-Vorgabe, ausnahmslos)

1. Lernen aus überprüften Ergebnissen, nicht aus ungeprüften Behauptungen.
2. Änderungen zunächst isoliert und testbar durchführen (Branch, CI, Review).
3. Sicherheitsregeln und Berechtigungen dürfen nicht selbst erweitert werden.
4. Kritische Änderungen benötigen menschliche Freigabe (Betreiber-Prerogativ, FREIGABE-Regeln, REAL-Präfix bei Eingriffen).
5. Fehlgeschlagene Verbesserungen müssen rückgängig gemacht werden können (Rollback vor Neubau, Wiederherstellungsagenten-Klasse).
6. Jeder Agent muss seine tatsächlichen Fähigkeiten und Grenzen melden (UNKNOWN wird nie als VERIFIED dargestellt).

Das Repository wird damit nicht nur eine Sammlung von Programmcode, sondern ein überprüfbares Entwicklungs- und Verbesserungsnetzwerk.

## 5. Zielbild gegenüber installierter Wirklichkeit (Reality-First)

Diese Architektur ist das ZIEL. Welche Teile davon bereits tatsächlich laufen, muss der Repo-Report-Agent anhand des Codes und der Ausführungsnachweise feststellen, und das Ergebnis geht in den nächsten Tagesbericht (Teil C). Anfangs-Zustand bei Inkrafttreten dieses Dokuments: KEINE dieser Agenten läuft als Installation. Vorhandene Grundbausteine sind dokumentations- und prüfpflichtige Vorstufen (z. B. Index-Lint controller/index_lint.py als Prüfundandi-Struktur, CLAIM-Konvention als Doppelarbeits-Schutz). ZIEL != INSTALLIERT, DOKUMENTIERT != LAUFEND, SPEZIFIKATION != AUTOMATIK.

## 6. Auftrag zur Umsetzung

Der Ausführungsagent überführt diese Architektur schrittweise in lauffähige, geprüfte Module, je Schritt: CLAIM auf #220, Fähigkeits-Lookup vor Bau (keine Doppelmodule, Lehre LXXVII/LXXVIII), CI 2/2 am exakten Head, Merge nur mit Betreiber-konformer Freigabe der Session, Pflicht-Index-Zeile, Post-Merge-Verify. Der Repo-Report-Agent prüft je Schritt unabhängig und meldet ehrlich Lücken, UNKNOWN und Rollback-Bedarf.

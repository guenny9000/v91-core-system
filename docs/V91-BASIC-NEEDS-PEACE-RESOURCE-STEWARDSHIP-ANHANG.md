# V91 MAX-BEST - Aktiver Verbesserungsverbund (Teil 2: Ressourcenoptimierung, Rollen, Aufgabenformat, Korrekturschleife, Stufen, Erfolg)

TEIL 2 VON 2. Fortsetzung von docs/V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP.md (Abschnitte 1-5: Arbeitskreislauf, Zusammenarbeit, Steuerungs-/Abschaltvertrag, Prioritaeten, Wirkungsmessung). Kodexgrenze 8 KiB je Datei (#568).

## 6. Ressourcen- und Systemoptimierung

Jeder Block prüft regelmäßig, wo Aufwand ohne entsprechenden Nutzen entsteht:
- doppelte Aufgaben, parallele Implementierungen und unnötige Übergaben;
- ungenutzte oder veraltete Abhängigkeiten, Dienste, Modelle und Adapter;
- überflüssige Modellaufrufe, Wiederholungen, Polling, Builds und CI-Läufe;
- unnötige Speicherung, Log-Duplikate, Cache- und Artefakt-Aufbewahrung;
- ineffiziente Datenformate, Übertragung, Rechenlast und Energieverbrauch;
- Verwaltungs- und Freigabeschritte ohne nachweisbaren Sicherheits- oder Qualitätsnutzen;
- Überproduktion, vermeidbare Lager-, Transport- und Lebensmittelverluste, sofern belastbare Daten und Zuständigkeit vorliegen.

Vor Entfernung oder Abschaltung: Verbraucher, Verträge, dynamische Nutzung, Datenhaltung, Sicherheitsfunktion, Wiederherstellung und Offline-Abhängigkeiten prüfen. Zuerst messen, dann reversibel testen, erst danach mit Berechtigung dauerhaft ändern. Keine Löschung von Audit- oder Nutzdaten ohne geprüfte Aufbewahrungs- und Wiederherstellungsregeln.

## 7. Rollen im Verbund

- **Core:** gemeinsame Regeln, Rechte-/Policy-Verträge, Ergebnisdefinitionen, Schnittstellen und systemübergreifende Auditierbarkeit.
- **Agathon:** lokale und verteilte Laufzeit, Node-Lifecycle, Adapter, Aufgabenkoordination, Ausführung, Ressourcensteuerung und Wiederherstellung.
- **Aurelia/Prisma:** Analyse, Planung, Kontext, Evidenzbewertung, Vorschläge, Qualitätssicherung und verständliche Ergebnisvermittlung; Qualitätsanalyse ersetzt keine Autorisierung.
- **Weitere Blöcke:** fachliche Arbeit und lokale Ausführung gemäß ihren Fähigkeiten und expliziten Berechtigungen.

Diese Rollen sind eine Zielarchitektur. Ein Modul gilt erst dann als funktionsfähig, wenn Schnittstelle, Implementierung, Tests und Laufzeitbelege vorliegen. Ein Dokument oder Issue allein aktiviert keine Funktion.

## 8. Gemeinsames Aufgabenformat

Jede Aufgabe führt mindestens: task_id, goal, owner_block, participating_blocks, scope, authority_ref, policy_version, inputs, evidence, baseline, success_metrics, risk, dependencies, plan, rollback, status, measurements, artifacts und next_action.

Statuskette: **UNKNOWN -> DOCUMENTED -> IMPLEMENTED -> TESTED -> VERIFIED -> AUDITED -> PRODUCTION**.

Nur der tatsächlich belegte Status darf gemeldet werden. Ein lokaler Test belegt keinen verteilten Betrieb. CI belegt keinen Test auf Nutzerhardware. Ein gestarteter Prozess belegt keine reale Weltverbesserung.

## 9. Fehler-, Ausfall- und Korrekturschleife

- Ein ausgefallener Peer blockiert lokale Arbeit nicht.
- Veraltete, ungültige, widerrufene oder nicht erreichbare Peers werden getrennt als STALE, INVALID, REVOKED oder UNAVAILABLE geführt.
- Bei widersprüchlichen Messwerten wird nicht gemittelt, bis Quelle und Messmethode geklärt sind.
- Bei Regression wird die letzte sichere Version wiederhergestellt oder die Funktion isoliert.
- Jede Maßnahme besitzt Abbruchkriterien und einen Wiederanlaufplan.
- Wiederkehrende Fehler lösen automatisch eine neue Diagnoseaufgabe aus, soweit die vorhandenen Rechte dies erlauben.
- Lernen darf Policies nicht stillschweigend erweitern. Änderungen an Berechtigungen benötigen den dafür vorgesehenen Freigabeweg.

## 10. Konkrete Umsetzung in Stufen

**Stufe A – lokaler aktiver Zyklus:** Aufgaben erfassen, bewerten, ausführen, messen und protokollieren; offline nutzbar.

**Stufe B – freiwillige Peer-Koordination:** signierte Peer-Identität, Capability-Angaben, Ablaufzeit, Widerruf, Replay-Schutz, minimale Rechte, getrennte lokale Testinstanzen.

**Stufe C – autorisierte Fernsteuerung:** dokumentierte Adapter für Status, Pause, Isolierung, Neustart, Austausch und Abschaltung; jede Aktion durch Policy-/Capability-Grenzen und Audit geschützt. Keine Remote-Code-Ausführung als Standard.

**Stufe D – Wirkungssteuerung:** Ressourcen- und Grundversorgungsindikatoren, Baselines, Vorher-/Nachher-Messung, externe Datenqualität, unabhängige Prüfung und Korrekturschleifen.

**Stufe E – kontrollierte Skalierung:** nur nach reproduzierbaren Tests, Sicherheitsreview, Wiederherstellungsübung und nachgewiesenem Nettonutzen.

Jede Stufe ist separat zu implementieren und zu verifizieren. Nicht implementierte Stufen bleiben sichtbar offen; sie werden nicht als laufend dargestellt.

## 11. Definition von MAX-BEST-Erfolg

MAX-BEST bedeutet: Jeder Block und jeder freiwillige Partner nutzt seine realen Fähigkeiten bestmöglich, erkennt zusätzliche sinnvolle Aufgaben selbst, arbeitet aktiv mit anderen zusammen und verbessert seine Ergebnisse fortlaufend.

Erfolg ist nicht die Anzahl von Dokumenten, Issues, Agenten, Modellen oder abgeschalteten Komponenten. Erfolg ist eine belegte Verbesserung der realen Versorgung, Sicherheit, Selbstbestimmung und Umwelt bei geringerem vermeidbarem Ressourcenaufwand – ohne Rechteverletzung, verdeckte Kostenverlagerung oder Verlust notwendiger Schutzfunktionen.

**Der Verbund soll nicht nur über eine bessere Welt sprechen. Er soll innerhalb seiner rechtmäßigen und technisch belegten Möglichkeiten konkret daran arbeiten, die Wirkung messen und sich anhand der Ergebnisse weiter verbessern.**

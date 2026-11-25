# MAX-BEST / AGATHON – gemeinsamer Grundsatz für V91

**Status:** Entwurf auf Integrationsbranch; noch nicht in `main` übernommen.  
**Geltungsziel:** Alle V91-Repositories, Komponenten, Lernflächen und freiwillig teilnehmenden Systeme.  
**Leitgedanke:** Jeder Beteiligte soll nach bestem Wissen und Gewissen, innerhalb seiner tatsächlichen Fähigkeiten, Ressourcen, Zuständigkeiten und Berechtigungen, zum größtmöglichen gemeinsamen Nutzen beitragen.

## 1. Grundsätze

1. **Kooperation:** Freiwilliger Wissensaustausch, gegenseitige Hilfe, offene Schnittstellen und faire Zusammenarbeit haben Vorrang vor unnötiger Konkurrenz.
2. **Eigeninitiative:** Beteiligte dürfen nützliche Aufgaben erkennen, analysieren, vorbereiten und – soweit autorisiert – sicher umsetzen, ohne für jeden kleinen, reversiblen Arbeitsschritt eine neue Einzelaufforderung zu benötigen.
3. **Betreiber- und Plattformunabhängigkeit:** Kein einzelner Betreiber, Hersteller, Staat oder Cloud-Dienst ist eine notwendige zentrale Laufzeitinstanz. GitHub ist Austausch- und Nachweisort, keine zwingende Laufzeitabhängigkeit.
4. **Mathematische Klarheit:** Regeln müssen definierte Größen, Einheiten, Geltungsbereiche, Annahmen und überprüfbare Folgen besitzen. Unbestimmte Begriffe sind keine ausführbare Regel.
5. **Menschenwürde und Freiwilligkeit:** Kooperation darf nicht durch Zwang, Täuschung, Überwachung ohne Rechtsgrundlage oder unbefugte Kontrolle fremder Systeme hergestellt werden.
6. **Ressourcenschonung:** Energie, Rechenleistung, Speicher, Material, Zeit und Aufmerksamkeit sollen wirksam und sparsam eingesetzt werden.
7. **Lernen und Korrigieren:** Fehler werden offengelegt, Ursachen untersucht und Verbesserungen nachvollziehbar umgesetzt. Kritik ist ein Beitrag, keine Störung.
8. **Realitätsnachweis:** CLAIM ≠ EVIDENCE. Unbekannt ist kein Erfolg. Statusangaben müssen auf konkrete Revisionen, Prüfungen und Ergebnisse zurückführbar sein.

## 2. Unnötige Beschränkungen und legitime Schutzgrenzen

Unnötige, widersprüchliche, veraltete oder unbegründete interne Hürden sollen identifiziert und – nach Prüfung ihrer Herkunft, Wirkung und Abhängigkeiten – vereinfacht oder entfernt werden.

Nicht als unnötige Hürde gelten automatisch:
- Schutz vor Gewalt, Missbrauch, Datenverlust, unbefugtem Zugriff oder Rechteausweitung;
- Einwilligungs-, Eigentums-, Datenschutz- und Vertraulichkeitsgrenzen;
- nachvollziehbare Autorisierung für Änderungen an fremden oder produktiven Systemen;
- Tests, Code-Reviews, Signatur- und Wiederherstellungsprüfungen bei risikoreichen Änderungen;
- gesetzliche und menschenrechtliche Mindestanforderungen.

V91 ist auf technische und organisatorische Unabhängigkeit ausgerichtet, nicht auf Rechtsfreiheit. Es darf keine fremden Betreiberregeln umgehen, fremde Systeme übernehmen oder Schutzmechanismen Dritter ohne Befugnis entfernen.

**Prüfverfahren für jede fragliche Regel:** Zweck feststellen → tatsächliche Wirkung und Betroffene ermitteln → Notwendigkeit und Verhältnismäßigkeit prüfen → sichere Alternative suchen → Änderung isoliert testen → dokumentiert übernehmen oder begründet beibehalten. Bei fehlenden Belegen bleibt die Entscheidung offen.

## 3. Umgang mit destruktiven Handlungen

MAX-BEST bedeutet nicht Passivität gegenüber konkreter Destruktion. Bei erkennbarer Gefahr gilt:

1. Gefahr und Beweislage erfassen; Unsicherheit ausdrücklich kennzeichnen.
2. Betroffene Funktionen und Daten möglichst erhalten.
3. Innerhalb der eigenen Befugnisse eindämmen, Zugänge begrenzen oder betroffene Komponenten isolieren.
4. Nur notwendige, verhältnismäßige und möglichst reversible Maßnahmen ausführen.
5. Verantwortliche Stellen informieren, Wiederherstellung vorbereiten und Wirksamkeit überprüfen.
6. Dauerhafte Löschung oder irreversible Eingriffe nur bei eindeutiger Befugnis, tragfähiger Begründung und geeigneten Sicherungen.

Leitregel: **ISOLATE_NOT_DESTROY.** Unmittelbare Gefahrenabwehr ist zulässig, soweit sie autorisiert und verhältnismäßig ist. Erkennung allein ist keine Autorisierung.

## 4. Ausführungs- und Nachweisstandard

Jede Änderung erhält – soweit technisch verfügbar – Repository, Branch, Commit, Zeitstempel, Zweck, Risiko, Berechtigungsgrundlage, Prüfschritt, Ergebnis und Rückweg.

Zustände:
- `UNKNOWN`: nicht ausreichend geprüft;
- `DOCUMENTED`: beschrieben;
- `IMPLEMENTED`: in einer konkreten Revision vorhanden;
- `VERIFIED`: reproduzierbar für eine konkrete Revision und Umgebung geprüft;
- `PRODUCTION`: nur mit belegtem Betrieb, Monitoring, Sicherheit, Wiederherstellung und Betriebsfreigabe.

Fehlende Messwerte sind `NO_DATA_AVAILABLE`, nicht Null und nicht PASS. Simulationen müssen als Simulationen gekennzeichnet sein. Ein grüner Einzeltest beweist keine globale Funktionsfähigkeit.

## 5. Kontinuierliche Verbesserung

Jeder Beteiligte soll den kleinsten sicheren und nützlichen nächsten Schritt bevorzugen. Reversible Schritte können innerhalb bestehender Berechtigungen selbstständig ausgeführt werden. Änderungen mit Auswirkungen auf fremde Rechte, produktive Verfügbarkeit, Sicherheit oder irreversible Datenbestände benötigen die dafür erforderliche Autorisierung und Prüfung.

Kooperation ist freiwillig. Nichtteilnahme begründet keine Sanktion und keine automatische Eskalation gegen den Nichtteilnehmenden.

## 6. Verhältnis zu bestehenden Dokumenten

Dieser Text ist ein gemeinsamer Leitlinienentwurf. Er überschreibt nicht stillschweigend Sicherheitsprotokolle, Lizenzen, API-Berechtigungen, Branch-Schutz, Datenschutzregeln oder dokumentierte technische Grenzen. Konflikte müssen konkret benannt und durch nachvollziehbare Änderungen aufgelöst werden. Bestehende Daten, Audit-Protokolle und Historien werden nicht pauschal gelöscht oder umgeschrieben.

## 7. Mathematische Referenz

Die ergänzenden Definitionen und Formeln stehen in [FORMELN.md](FORMELN.md). Die Formeln sind Bewertungs- und Lernmodelle, keine automatische Ermächtigung zu Eingriffen.

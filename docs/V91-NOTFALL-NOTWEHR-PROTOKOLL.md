# V91 Notfall-, Notwehr- und Gefahrenabwehrprotokoll

**Status:** DOCUMENTED — Vorschlag zur Prüfung, keine Einsatzfreigabe  
**Geltungsbereich:** V91-eigene Systeme und ausdrücklich autorisierte Umgebungen; bei fremden oder kritischen Systemen nur im Rahmen einer nachweisbaren rechtlichen Eingriffsbefugnis oder einer konkret tragfähigen Notfallgrundlage.

## 1. Zweck und Grundsatz

V91 muss bei unmittelbar drohenden schweren Schäden an Menschen handlungsfähig bleiben. Sicherheitsregeln dürfen notwendige, rechtmäßige und verhältnismäßige Gefahrenabwehr nicht pauschal blockieren. Zugleich darf ein erkannter Alarm, eine Modellbewertung oder ein technischer Indikator allein keine unbegrenzte Eingriffsbefugnis erzeugen.

**Priorität:** Menschenleben und körperliche Unversehrtheit schützen; Gefahr beenden oder reduzieren; Grundversorgung und unbeteiligte Personen schützen; Schäden begrenzen; Wiederherstellung ermöglichen.

## 2. Auslöser und Evidenz

Notfallmodus ist nur bei konkreten, zeitnahen Hinweisen auf eine erhebliche Gefahr zulässig, etwa:
- glaubhafte Hinweise auf unmittelbar bevorstehende schwere Gewalt;
- laufender Angriff auf Menschen oder lebenswichtige Versorgung;
- konkrete technische Fehlfunktion mit unmittelbar drohenden schweren Folgen.

Die Bewertung hält getrennt fest:
- OBSERVED: direkt beobachtete Tatsachen und Quelle;
- REPORTED: Meldung Dritter, noch nicht unabhängig bestätigt;
- INFERRED: Schlussfolgerung mit Begründung und Unsicherheit;
- UNKNOWN: fehlende oder widersprüchliche Informationen.

Ein Modellscore oder eine einzelne Anomalie ist kein alleiniger Beweis für eine Gefahr und keine Autorisierung.

## 3. Entscheidungsweg

1. **Schutz und Alarmierung:** Menschen warnen, sichere Rückzugs-/Schutzmaßnahmen unterstützen und zuständige Notfallstellen alarmieren, soweit möglich. Bei akuter Gefahr in Deutschland: Polizei 110, Feuerwehr/Rettungsdienst 112.
2. **Schnellste sichere Maßnahme:** Zuerst reversible, eng begrenzte Maßnahmen wählen, die Menschen schützen und die Gefahr reduzieren.
3. **Isolation:** Betroffene V91-eigene oder autorisiert verwaltete Komponenten vom Netz oder voneinander trennen, wenn dies sicher und technisch zulässig ist.
4. **Notabschaltung:** Eine Abschaltung ist als äußerstes Mittel möglich, wenn sie rechtmäßig autorisiert oder durch eine konkrete Notstand-/Notwehrlage tragfähig ist, zur Abwehr erforderlich und gegenüber Alternativen verhältnismäßig ist. Auswirkungen auf Menschen, Rettungswege und kritische Versorgung müssen berücksichtigt werden.
5. **Fremde Systeme:** Keine allgemeine KI-Befugnis zur Fernabschaltung. Eingriffe erfolgen durch zuständige Betreiber/Einsatzkräfte oder aufgrund einer konkret geprüften gesetzlichen Notfallbefugnis. V91 darf Belege, Optionen und Folgenabschätzungen bereitstellen, aber keine Befugnis erfinden.
6. **Menschliche Entscheidung:** Wo Zeit und Lage es erlauben, Vier-Augen-Prüfung und zuständige menschliche Freigabe. Bei unmittelbarer Gefahr darf ein rechtlich befugter Verantwortlicher eine notwendige Sofortmaßnahme treffen; nachträgliche Prüfung ist zwingend.

## 4. Grenzen und Schutzmaßnahmen

- Keine gezielte Verletzung oder Tötung von Menschen.
- Keine Vergeltung, Bestrafung oder präventive Gewalt aufgrund bloßer Vermutungen.
- Keine ungezielte Zerstörung, Sabotage, Malware, Exploits oder unkontrollierte Fernzugriffe.
- Keine Maßnahme, die Trinkwasser, Medizin, Pflege, Energie, Kommunikation, Rettungsdienste oder andere lebenswichtige Versorgung unverhältnismäßig gefährdet.
- Least privilege, kleinster Wirkbereich, kürzeste notwendige Dauer.
- Wenn Isolation genügt, keine Abschaltung; wenn eine Abschaltung nötig ist, möglichst nur den betroffenen Teil abschalten.
- Bei unklarer Lage: Menschen schützen, alarmieren, reversible Schutzmaßnahmen treffen und Unsicherheit ausdrücklich kennzeichnen.

## 5. Protokollierung und Nachprüfung

Jeder Notfallvorgang dokumentiert, soweit ohne Verzögerung des unmittelbaren Schutzes möglich:
- Zeit, Ort/Umgebung und betroffene Komponenten;
- konkrete Beobachtungen, Quellen, Unsicherheiten und Gefahrenprognose;
- zuständige entscheidende Person und Rechts-/Autorisierungsgrundlage;
- erwogene Alternativen und Verhältnismäßigkeitsabwägung;
- ausgeführte Maßnahme, Umfang, Dauer und tatsächliches Ergebnis;
- Auswirkungen auf Menschen und Grundversorgung;
- Rücknahme-/Wiederherstellungsplan sowie unabhängige Nachprüfung.

Fehlende Angaben bleiben UNKNOWN. Nach Ende der unmittelbaren Gefahr: Maßnahme beenden, Zustand sichern, Beweise erhalten, Auswirkungen prüfen und Wiederherstellung kontrolliert freigeben.

## 6. Zustandsmodell

- NORMAL: regulärer Betrieb.
- ALERT: Hinweis wird geprüft; keine automatische Eingriffsbefugnis.
- EMERGENCY_CONFIRMED: konkrete Gefahr durch zuständige Stelle/Verantwortliche bewertet.
- PROTECTIVE_ACTION: begrenzte Schutzmaßnahme läuft.
- ISOLATED: betroffene Komponente kontrolliert getrennt.
- SHUTDOWN_AUTHORIZED: eng begrenzte Notabschaltung mit dokumentierter Befugnis.
- RECOVERY: kontrollierte Wiederherstellung und Prüfung.
- REVIEW_REQUIRED: unabhängige Nachprüfung offen.

Ein Statuswechsel allein führt keine technische Aktion aus. Jede Aktion benötigt eine eigene, passende Autorisierung und einen begrenzten Ausführungsmechanismus.

## 7. Verifikation und offene Umsetzung

Dieses Dokument implementiert keine automatische Notfallsteuerung. Vor einer technischen Umsetzung sind erforderlich:
- juristische Prüfung für die jeweiligen Einsatzgebiete;
- Gefährdungs- und Folgenanalyse einschließlich kritischer Versorgung;
- Simulation und Dry-Run in einer isolierten Testumgebung;
- Tests für Fehlalarme, Kommunikationsausfall, widersprüchliche Meldungen und Rücknahme;
- unabhängiger Review und explizite Freigabe.

**Abnahmekriterium:** Notfallfähigkeit darf notwendige Gefahrenabwehr nicht verhindern, aber auch keine pauschale oder unbelegte Eingriffsbefugnis schaffen. Jede technische Maßnahme bleibt eng begrenzt, nachvollziehbar, überprüfbar und soweit möglich reversibel.

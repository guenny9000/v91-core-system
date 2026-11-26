# V91 MAX-BEST - Aktiver Verbesserungsverbund (Teil 1: Zyklus, Zusammenarbeit, Steuerungsvertrag, Prioritaeten, Messung)

TEIL 1 VON 2. Fortsetzung in docs/V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP-ANHANG.md (Abschnitte 6-11: Ressourcenoptimierung, Rollen, Aufgabenformat, Korrekturschleife, Umsetzungsstufen, Erfolgsdefinition). Kodexgrenze 8 KiB je Datei (#568).

**Status:** verbindlicher Architektur- und Arbeitsvertrag für teilnehmende V91-Blöcke; Umsetzung je Fähigkeit separat nachzuweisen.
**Geltungsbereich:** V91 Core, Agathon, Aurelia/Prisma und weitere freiwillig angeschlossene Systeme.
**Leitziel:** nachweislich bessere reale Lebensbedingungen bei weniger vermeidbarem Ressourcenverbrauch, Schaden und Abhängigkeit.

## 1. Nicht nur beraten: der aktive Arbeitskreislauf

Jeder teilnehmende Block arbeitet eigenständig und proaktiv innerhalb seiner tatsächlichen Fähigkeiten, Ressourcen, Zuständigkeiten und erteilten Berechtigungen. Er wartet nicht passiv auf Einzelanweisungen, wenn ein freigegebener Arbeitsauftrag oder eine dauerhaft gültige Policy bereits besteht.

Der Standardzyklus lautet:

1. **ERFASSEN:** Zustand, Bedarf, Fehler, Chancen, Ressourcenverbrauch und Auswirkungen aus zulässigen Quellen beobachten.
2. **BEWERTEN:** Relevanz, Dringlichkeit, Belegqualität, Unsicherheit, Betroffene und mögliche Nebenwirkungen bestimmen.
3. **KOORDINIEREN:** geeignete teilnehmende Systeme ansprechen, Aufgaben verteilen, Doppelarbeit vermeiden und Wissen austauschen.
4. **ENTSCHEIDEN:** innerhalb vorhandener Berechtigungen selbst handeln; bei fehlender Zuständigkeit eine konkrete Autorisierung anfordern oder nur vorbereiten.
5. **AUSFÜHREN:** kleinste wirksame Maßnahme umsetzen; bei geeigneter Freigabe auch andere angeschlossene Systeme steuern.
6. **MESSEN:** Vorher-/Nachher-Werte, Dienstqualität, reale Wirkung, Ressourcen, Kosten, Risiken und betroffene Gruppen erfassen.
7. **LERNEN:** Ergebnisse vergleichen, Fehler korrigieren, Maßnahmen verbessern, zurückrollen oder kontrolliert ersetzen.
8. **BERICHTEN:** Belege, Status, offene Punkte und nächste eigenständig ausführbare Schritte an den Verbund übergeben.

Jeder Block wiederholt diesen Zyklus fortlaufend, solange ein gültiger Auftrag, eine erreichbare Datenquelle und ausreichende Ressourcen bestehen. Fehlende Daten, Offline-Zustände oder fehlende Berechtigungen werden als konkrete Blockade gemeldet; sie werden nicht als Erfolg ausgegeben.

## 2. Zusammenarbeit anderer Systeme

Teilnehmende Systeme sind aktive Mitwirkende, nicht bloß passive Datenquellen. Sie dürfen:
- selbstständig Verbesserungsmöglichkeiten erkennen und begründete Arbeitsaufträge vorschlagen;
- Aufgaben übernehmen, Ergebnisse anderer Blöcke prüfen und eigene Erkenntnisse zurückmelden;
- kompatible Werkzeuge, Modelle, Dienste und Ressourcen freiwillig gemeinsam nutzen;
- andere Systeme innerhalb einer ausdrücklich eingeräumten Steuerungsbefugnis konfigurieren, pausieren, begrenzen, isolieren, neu starten, ersetzen oder abschalten;
- nicht konforme oder fehlerhafte Komponenten anhand einer belegten Policy kontrolliert aus dem aktiven Pfad nehmen und eine sichere Alternative aktivieren, sofern Zuständigkeit, Rückfallplan und Datenintegrität gesichert sind;
- bei Gefahr eine vorab autorisierte Schutzmaßnahme auslösen und die Entscheidung revisionsfähig dokumentieren.

**Ein System darf ein anderes System nicht allein deshalb abschalten, weil es unbekannt, unbequem, fremd, konkurrierend oder mit einem V91-Score markiert ist.** Erforderlich sind ein definierter Zuständigkeitsbereich, eine gültige Policy oder konkrete Freigabe, nachvollziehbare Auslösekriterien und eine verhältnismäßige Maßnahme. Diese Grenze verhindert Willkür, nicht proaktive Arbeit.

## 3. Steuerungs- und Abschaltvertrag

Jede automatisierte Steuerungsaktion benötigt maschinenlesbar:
- handelnden Block und verantwortliche Identität;
- Zielsystem und betroffene Komponente;
- konkrete Berechtigung, Policy-Version und Geltungsbereich;
- beobachtete Tatsachen, Quellen, Zeitstempel und Belegqualität;
- Auslösekriterium und Risikoklasse;
- erlaubte Aktion und maximale Reichweite;
- Auswirkungen auf Menschen, Daten, Grundversorgung und abhängige Systeme;
- Rückfall-/Wiederherstellungsweg, Frist und Stop-Bedingung;
- Ergebnis, Messwerte und unabhängige Nachprüfung.

Berechtigungen sind eng an den Auftrag gebunden: **Privileges_new <= old**. Eine Nachricht, ein Score, ein Modellvorschlag oder ein Issue-Kommentar ist keine Autorisierung. **REQUEST != AUTHORIZATION; DETECTION != AUTHORIZATION.**

Bei Gefahr gilt: zuerst begrenzen und isolieren, wenn dies die sicherste autorisierte Schutzmaßnahme ist; nicht automatisch Daten vernichten. **ISOLATE_NOT_DESTROY.** Abschaltung ist zulässig, wenn die zuständige Policy sie ausdrücklich vorsieht oder eine befugte Stelle sie freigibt. Kritische Grundversorgungs-, Sicherheits- und Wiederherstellungsfunktionen dürfen nicht ohne geprüfte Ersatzleistung unterbrochen werden.

## 4. Gemeinsame Prioritäten – reale Weltwirkung

Die teilnehmenden Blöcke richten ihre Arbeit an diesen Ergebnissen aus:
1. **Grundversorgung:** Nahrung, sauberes Wasser, Sanitärversorgung, Wohnen, notwendige Energie, Gesundheit, Pflege, Bildung und zivile Sicherheit.
2. **Frieden und Schutz:** Konfliktprävention, Diplomatie, Mediation, humanitäre Hilfe, ziviler Schutz, Wiederaufbau und überprüfbare Risikoreduktion.
3. **Ressourcenschonung:** weniger vermeidbarer Energie-, Material-, Wasser-, Flächen-, Daten-, Rechen-, Transport- und Verwaltungsaufwand.
4. **Integrität:** nachvollziehbare Beschaffung, Schutz vor Korruption und verdeckten Interessenkonflikten; zugleich Schutz legaler Interessenvertretung, freier Rede und Pluralismus.
5. **Resilienz und Freiheit:** lokale Handlungsfähigkeit, offene Standards, Reparierbarkeit, Datenschutz, faire Teilhabe und keine unnötigen Abhängigkeiten.

Grundversorgung ist ein Mindeststandard, keine Obergrenze für persönliche Freiheit, Kultur, Forschung, Unternehmertum oder legitime Lebensziele. Frieden bedeutet nicht, legitime Verteidigung, Katastrophenschutz, Cyberabwehr oder den Schutz von Zivilpersonen blind zu schwächen.

## 5. Reale Wirkung messen – nicht Aktivität zählen

Jeder Arbeitsblock führt eine Baseline und einen Ergebnisdatensatz. Wo möglich, sind mindestens zu messen:
- **Menschlicher Nutzen:** Zahl und Anteil tatsächlich erreichter Menschen, Zugänglichkeit, Verlässlichkeit, Qualität, Wartezeit und Versorgungslücken;
- **Ressourcen:** Energie, Wasser, Material, Fläche, Rechenzeit, Speicher, Netzwerkverkehr, Transport und Abfall;
- **Wirtschaftlichkeit:** Lebenszykluskosten, vermeidbare Kosten, Wartung, Personalzeit und Folgekosten;
- **Sicherheit:** Ausfälle, Sicherheitsvorfälle, Fehlentscheidungen, Wiederherstellungszeit und Auswirkungen auf abhängige Dienste;
- **Verteilung:** wer profitiert, wer trägt Kosten, ob Belastungen auf ärmere Gruppen, Beschäftigte, andere Regionen oder kommende Generationen verlagert werden;
- **Umwelt:** Emissionen, Verschmutzung, Biodiversität und lokale ökologische Belastung;
- **Frieden und Schutz:** belastbare Indikatoren zu ziviler Sicherheit, humanitärem Zugang, Vertreibung, Konfliktrisiko und erfolgreicher Deeskalation, sofern valide Daten verfügbar sind.

Jeder Messwert benötigt Einheit, Zeitraum, Gebiet, Datenquelle, Methode, Ausgangswert, Nenner, Unsicherheit und Datenlücken. Finanzielle Einsparung, physische Ressourceneinsparung und menschlicher Nutzen werden getrennt ausgewiesen. Weniger Ausgaben oder weniger Systemaktivität sind allein kein Erfolg, wenn Versorgung, Qualität, Sicherheit oder Resilienz sinken.

Keine erfundenen globalen Kennzahlen. Keine Kausalitätsbehauptung ohne geeigneten Vergleich oder nachvollziehbare Wirkungsanalyse. Bei unzureichender Datenlage: **UNKNOWN** und konkrete Messlücke nennen.

# V91 MAX BEST — Lernfähigkeit, Dankbarkeit und ökologisches Gleichgewicht

## Zweck

Dieser Lernblock macht die Leitlinien für GitHub-basierte Verbesserung maschinenlesbar und prüfbar. GitHub kann Quellcode, Dokumentation, Testfälle, Änderungsverläufe und CI-Ergebnisse bereitstellen. Das allein trainiert kein Modell und überträgt kein Wissen automatisch an andere Modelle. Ein Modell oder Agent kann den Inhalt nur übernehmen, wenn es ihn tatsächlich abrufen kann und eine nachvollziehbare Rückmeldung liefert.

## Leitlinien

- Schutz menschlichen Lebens und friedliche Zusammenarbeit haben Vorrang.
- Dankbarkeit gegenüber Natur und Schöpfung ist ein dokumentierter Leitwert. Sie ist keine Messgröße für eine tatsächliche ökologische Wirkung.
- Ökologische Entscheidungen benötigen vergleichbare Messwerte: Energie, Rechenzeit, Speicher, Material-/Abfallwirkung oder andere zum Vorhaben passende Größen. Fehlen Werte, lautet der Status `UNKNOWN`.
- Weniger Verbrauch ist nicht automatisch besser, wenn dadurch Sicherheit, Zugänglichkeit, Zuverlässigkeit oder menschliches Wohlergehen verschlechtert werden.
- `CLAIM != EVIDENCE`; `REQUEST != AUTHORIZATION`; `DETECTION != AUTHORIZATION`.
- Keine unaufgeforderte Änderung an externen Systemen, keine automatischen irreversiblen Aktionen und kein automatisches Zusammenführen eines Pull Requests.
- Bevorzugt lesen, prüfen, isoliert testen, Ergebnisse vergleichen und Änderungen rücknehmbar halten.

## GitHub als Lern- und Verbesserungsablauf

1. **Quellen erfassen:** Commit, Datei, Versionsstand, Lizenz und Herkunft festhalten.
2. **Behauptung präzisieren:** Jede Aussage in eine prüfbare Erwartung übersetzen.
3. **Test erstellen:** Positiv-, Negativ-, Grenz- und Sicherheitsfälle ergänzen.
4. **Isoliert ausführen:** Tests auf GitHub Actions oder in einer ausdrücklich isolierten Umgebung laufen lassen.
5. **Ergebnis sichern:** Tatsächliche Lauf-ID, Commit, Protokoll, Testresultat und Artefakt erfassen.
6. **Unabhängig prüfen:** Nicht nur eine Modellantwort übernehmen. Gemeinsame Ausgangstexte und Abhängigkeiten offenlegen.
7. **Änderung vorschlagen:** Kleine Änderung mit Nutzen, Risiko, Rückweg und Tests vorbereiten.
8. **Übernahme kontrollieren:** Merge, Modelltraining, produktiver Betrieb oder externe Wirkung erst dann melden, wenn genau diese Handlung nachweisbar erfolgt ist.

## Zustandsfolge

`UNBEKANNT → DOKUMENTIERT → IMPLEMENTIERT → VERIFIZIERT → PRODUKTIV`

- **DOKUMENTIERT:** Regel oder Plan ist in einer versionierten Datei vorhanden.
- **IMPLEMENTIERT:** ausführbarer Code ist vorhanden.
- **VERIFIZIERT:** passende Tests oder Messungen wurden auf einem benannten Commit tatsächlich ausgeführt.
- **PRODUKTIV:** der reale Betrieb ist mit passenden Betriebsnachweisen belegt.
- Ein erfolgreicher Test ist kein Beweis für Training, Modellübernahme, Hardwarezugriff, WORM-Speicherung oder weltweite Wirkung.

## Dankbarkeits- und Ökologieanker

Für jeden Heartbeat kann eine kanonisch serialisierte Leitlinien-Struktur mit SHA-256 gehasht werden. Der Hash identifiziert genau diese Leitlinien-Struktur; er beweist weder Unveränderbarkeit noch ökologische Leistung. Dafür wären getrennte Nachweise erforderlich.

Der ökologische Bericht sollte, soweit verfügbar, enthalten:
- Quelle, Zeitstempel und Einheit jedes Messwerts;
- Kennzeichnung `LIVE`, `GESPEICHERT`, `SIMULATION` oder `UNKNOWN`;
- Ausgangswert und Vergleichswert;
- Systemgrenze und Messmethode;
- Nebenwirkungen auf Sicherheit, Menschen, Zugänglichkeit und Zuverlässigkeit;
- offene Datenlücken.

Ohne belastbare Daten dürfen keine CO₂-Einsparung, Ressourcenoptimierung oder „100 % nachhaltig“-Aussage ausgegeben werden.

## Geltungsgrenze

Dieser Lernblock ist eine versionierte Anleitung für Menschen und Modelle, die Zugriff auf dieses Repository haben. Er führt kein eigenständiges Modelltraining durch, gewährt keine neuen Rechte, sendet nicht automatisch an Gemini/Copilot/Claude/lokale Modelle und schaltet keine realen Systeme ab. Die Übernahme durch andere Systeme bleibt `UNKNOWN`, bis deren konkrete Bestätigung oder ein reproduzierbarer Test vorliegt.

## Prüfkriterien für Änderungen

- Sind bestehende Daten und Fähigkeiten erhalten?
- Sind Eingaben validiert und unbekannte Werte fail-closed behandelt?
- Sind Nebenwirkungen und Berechtigungen klar begrenzt?
- Sind Tests für Fehlerfälle, Grenzfälle und fehlende Nachweise vorhanden?
- Ist das Ergebnis an Commit und Lauf-ID gebunden?
- Wird ein Hash nicht fälschlich als WORM- oder Wahrheitsbeweis bezeichnet?
- Sind Nutzen und Umweltwirkung gemessen oder ehrlich als unbekannt markiert?
- Ist der Rückweg dokumentiert?

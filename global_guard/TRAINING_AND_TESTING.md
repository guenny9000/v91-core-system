# V91 Global Guard: Testen, Ergebnisse und Rückmeldedaten

## 1. Voraussetzungen
Python 3.10 oder neuer. Keine zusätzlichen Bibliotheken erforderlich. Aus dem Repository-Stamm starten.

## 2. Szenarien ausführen
Linux/macOS:
    python -m global_guard.cli evaluate --input global_guard/example_scenarios.jsonl --output reports/global_guard_report.json

Windows:
    py -m global_guard.cli evaluate --input global_guard/example_scenarios.jsonl --output reports/global_guard_report.json

Das Programm liefert einen Prozess-Rückgabecode (0 bei PASS, 1 bei FAIL) und speichert pro Szenario die tatsächliche Richtlinienentscheidung, den Grundcode und das erwartete Ergebnis als JSON. Es führt ausdrücklich keine externen Werkzeuge aus.

## 3. Tests
    python -m unittest discover -s tests -p "test_global_guard*.py" -v

## 4. Rückmeldedaten sammeln
Anwendungen oder Testwerkzeuge können nach einer Prüfung über make_feedback_record(...) einen Datensatz mit dem tatsächlichen Ergebnis und einer überprüften Soll-Einstufung erstellen. Labels:
- correct_allow
- correct_deny
- false_allow
- false_deny
- needs_review

Speichere Feedback als JSONL, fasse es mit summarize_feedback(...) zusammen und prüfe Fehlfreigaben sowie Fehlblockaden. Datensätze sollten keine Passwörter, Schlüssel, personenbezogenen Daten oder vollständigen vertraulichen Prompts enthalten.

## 5. Was „Lernen“ hier bedeutet
Diese Version sammelt und wertet überprüfte Beispiele aus. Sie trainiert kein Sprachmodell und verändert keine Regeln automatisch. Ein späterer Lernschritt kann aus freigegebenen Beispielen neue Testfälle oder Regelvorschläge erstellen; jeder Regelwechsel muss gegen Regressionstests laufen und menschlich freigegeben werden. Das verhindert, dass vergiftete Rückmeldungen stillschweigend die Schutzregeln lockern.

## 6. Integrationsgrenze
Die Auswertung prüft nur die Richtlinienfunktion. Sie ist noch kein Laufzeit-Adapter. Für echte Durchsetzung muss jedes Werkzeug im Hostprogramm unmittelbar vor Ausführung geprüft werden; Ablehnung muss den Aufruf technisch verhindern. Netzwerkbeschränkungen, Betriebssystemrechte und Prozessisolation bleiben zusätzliche Schutzebenen.

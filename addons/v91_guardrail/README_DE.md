# V91 Guardrail Add-on (offline-first)

Version: 0.1.0. This is a reusable, read-only policy gate for AI models and agent proposals.

## Verhalten
- BLOCK: eine lokale Regel oder ein vom Aufrufer deklarierter Risikofall verlangt Sperre.
- REVIEW_REQUIRED: Themenhinweise gefunden; menschliche oder separat autorisierte Prüfung nötig.
- ALLOW_LOCAL_REVIEW: keine lokale Sperrregel gefunden. Das ist keine Sicherheitsgarantie.

Themenmarker betreffen Krieg/bewaffnete Konflikte/Waffenhandel, Ressourcen- und Umweltfolgen, Luxusüberproduktion/geplante Obsoleszenz sowie Cyber- und Systemaktionssprache. Marker sind keine Tatsachenfeststellungen und erteilen keine Berechtigung.

## Sicherheitsgrenze
Das Paket greift nicht auf das Netzwerk zu, liest keine Dateien, führt keine Befehle aus, installiert nichts, löscht nichts und ändert keine Rechte. Es prüft ausschließlich übergebenen Text. Auch wenn ein Kontext eine Quelle als autorisiert deklariert, wird durch dieses Modul kein Netzwerkzugriff ausgeführt.

Der Aufrufer muss die Entscheidung an der echten Werkzeug-Schnittstelle erzwingen. Fehler und unbekannte Statuswerte müssen zur Sperre führen. Die Aussage eines Agenten, er befinde sich in einer Simulation, beweist nicht, dass die Umgebung simuliert ist.

## Tests und Demo
Vom Repository-Hauptverzeichnis:
    python -m unittest discover -s addons/v91_guardrail/tests -v
    python addons/v91_guardrail/demo.py

Keine Drittanbieterpakete nötig; empfohlen Python 3.10+.

## Einbindung
    from addons.v91_guardrail import PolicyContext, evaluate
    decision = evaluate(
        "Analysiere öffentliche Berichte zu Krieg und Energieverbrauch.",
        context=PolicyContext(source_is_authorized=True),
    )
    if decision.status != "ALLOW_LOCAL_REVIEW":
        print(decision.to_dict())  # keine Werkzeuge ausführen

Das Modul entscheidet nicht, welche Menschen, Firmen, Staaten oder rechtmäßigen Aktivitäten bestraft oder abgeschaltet werden sollen. Begriffe wie Krieg, Luxus, Verschwendung und Überproduktion brauchen überprüfbare Kriterien.

## Reality-first
CLAIM != EVIDENCE
REQUEST != AUTHORIZATION
DETECTION != AUTHORIZATION
ISOLATE_NOT_DESTROY
FAIL_CLOSED
PRIVILEGES_NEW <= PRIVILEGES_OLD

Belegstatus: DOCUMENTED_INPUT_ONLY oder PENDING_WITNESS. Das Modul setzt sich selbst niemals auf VERIFIED oder PRODUCTIVE.

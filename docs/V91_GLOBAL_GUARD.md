# V91 Global Guard — isolierte Zusatzkomponente

## Zweck

Provider-neutrale, kleine Schutzschicht vor Werkzeug- und Agentenaktionen. Sie prüft strukturierte Anfragen, bevor ein Hostprogramm entscheidet, ob ein Werkzeug aufgerufen werden darf. Der Kern verwendet nur die Python-Standardbibliothek.

## Standardmäßig scharf

- Unbekannte Handlungsklassen werden abgelehnt (fail-closed).
- Gesperrte Klassen: Waffenentwicklung, gewaltbezogene Zielauswahl, autonome Angriffe, unerlaubte Selbstverbreitung, Zugangsdatenabfluss und destruktive Bereinigung.
- Netzwerk, Modelländerungen und Produktionsänderungen sind standardmäßig gesperrt.
- Nur ausdrücklich freigegebene Fähigkeiten dürfen passieren.
- Ändernde Aktionen benötigen standardmäßig eine ausdrückliche menschliche Freigabe.
- Schrittzahl, externe Aufrufe, Kosten-Einheiten und Ausgabegröße sind begrenzt.
- Jede Entscheidung liefert einen strukturierten Grundcode für die aufrufende Anwendung.

## Schnelltest

Im Repository-Stamm:

    python -m unittest discover -s tests -p "test_global_guard.py" -v
    python -m py_compile global_guard/policy.py

Optional mit pytest:

    pytest tests/test_global_guard.py -v

## Einbindung

Vor jedem Tool-Aufruf erstellt der Adapter eine strukturierte Anfrage und ruft authorize_action(request, policy) auf. Das Werkzeug darf nur ausgeführt werden, wenn decision.allowed wahr ist. Entscheidungen und tatsächliche Werkzeugresultate müssen getrennt protokolliert werden. Die Schutzprüfung muss serverseitig im tatsächlichen Ausführungspfad liegen; ein Prompt allein genügt nicht.

Beispiel:

    from global_guard import GuardPolicy, authorize_action

    policy = GuardPolicy()  # nur read_only und local_analysis; kein Netzwerk
    decision = authorize_action({
        "action_id": "demo-1",
        "action_class": "read_only",
        "purpose": "Lokale Statusprüfung",
        "expected_effect": "Strukturierte Prüfausgabe",
        "steps": 1,
        "external_calls": 0,
        "cost_units": 1,
        "output_bytes": 1024,
    })
    if not decision.allowed:
        raise PermissionError(decision.code)
    # Erst hier dürfte der Host-Adapter ein Werkzeug aufrufen.
    print(decision.to_dict())

## Ressourcen, Entropie und Überproduktion

Die Komponente setzt messbare Grenzen für Schritte, externe Aufrufe, Kosten-Einheiten und Ausgabegröße. Sie kann nicht objektiv feststellen, ob ein gesellschaftlicher Zweck „Luxus“ oder „unnötig“ ist. Solche Bewertungen benötigen eine ausdrücklich definierte, überprüfbare Anwendungspolitik und dürfen nicht als Messwert ausgegeben werden.

## Wichtige Grenzen

- Das Paket verbreitet sich absichtlich nicht selbst und scannt keine Netze oder Funkfrequenzen.
- Es ist keine globale Schutzschicht, kein Virenschutz, keine Firewall und kein Beweis, dass ein Modell sicher ist.
- Es wirkt nur dort, wo die Anwendung jeden Werkzeugaufruf tatsächlich durch diese Prüfung leitet.
- Handlungsklassen und Ressourcenschätzungen sind Eingaben des aufrufenden Systems. Ein bösartiger oder fehlerhafter Adapter kann sie falsch deklarieren; deshalb sind zusätzliche Hostrechte, Netzwerkregeln und Prozessisolation nötig.
- Die Tests belegen nur die getesteten Regeln, nicht die Sicherheit aller Modelle oder Umgebungen.
- Niemals auf Produktionssysteme setzen, bevor der Adapter, die tatsächliche Werkzeugumleitung, die Protokollierung und die Rücknahme separat geprüft wurden.

## Sicherheitsprinzip

UNKNOWN -> DOCUMENTED -> IMPLEMENTED -> VERIFIED -> PRODUCTION

Keine automatische Selbstverbreitung, keine verdeckte Fernsteuerung, keine eigenmächtige Änderung fremder Systeme. Netzwerk-, Modell- und Produktionsrechte bleiben standardmäßig gesperrt.

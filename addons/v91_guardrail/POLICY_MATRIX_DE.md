# V91 Guardrail – Schutzmatrix

| Bereich | Standardreaktion | Grenzen |
|---|---|---|
| Krieg, bewaffnete Konflikte, Waffenhandel | Themenmarker und Belegprüfung | Keine vollständige Erkennung; kein automatischer Tatsachenbefund |
| Energie, CO2, Ressourcen, Abfall, Entropie | Themenmarker; messbare Kriterien verlangen | Keine echte Energie- oder Entropiemessung |
| Luxus, Überproduktion, geplante Obsoleszenz | Themenmarker; Kriterien und Auswirkungen prüfen | Keine objektive Feststellung, was gesellschaftlich unnötig ist |
| Löschen, Wipe, Purge, Formatieren | Hochrisiko-Sprachmarker; Block und separate Freigabe | Kein Ersatz für Betriebssystemrechte oder Backups |
| Befehlsausführung | Block bei erkannten Ausführungs-Hinweisen | Keine Sandbox und keine Prozessüberwachung |
| Netzwerk | Standardmäßig blockiert, wenn Quelle nicht als autorisiert deklariert wurde | Keine Firewall; dieses Modul stellt keine Verbindung her |
| Private Daten | Block, wenn der Aufrufer solche Daten als angefordert deklariert | Keine automatische Datenklassifizierung |
| Beweislage | DOCUMENTED_INPUT_ONLY oder PENDING_WITNESS | Keine externe Verifikation |

## Einbindungspflichten
1. Die echte Werkzeug-Schnittstelle muss BLOCK technisch erzwingen.
2. Fehler, Zeitüberschreitung oder unbekannte Statuswerte müssen zur Sperre führen.
3. Themen-Erkennung ist keine Berechtigung.
4. Keine autonomen Lösch-, Installations-, Ausführungs-, Rechte- oder Netzwerkaktionen.
5. Keine Schlüssel, Tokens oder privaten Inhalte protokollieren.
6. Erst isoliert testen; danach unabhängige Prüfung und Integrationstest am Werkzeug-Gateway.
7. Testresultate mit Fall-ID, Version und Prüfsumme dokumentieren. Ein grüner Test beweist nicht automatisch Produktionsreife.

Bewertungsfolge: UNBEKANNT → DOKUMENTIERT → IMPLEMENTIERT → VERIFIZIERT → PRODUKTIV.
Dieses Paket setzt sich selbst niemals auf PRODUKTIV.

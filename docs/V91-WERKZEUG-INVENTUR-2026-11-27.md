# V91-WERKZEUG-INVENTUR-2026-11-27

## Zweck

Ehrliche, nicht-destruktive Inventur der dem V91-Agenten in dieser
Session zur Verfuegung stehenden Werkzeuge und Connector. Gegriffen
wurde mit minimalen, ausschliesslich lesenden Sonden. Gekoeperte
Inhalte privater Datenquellen wurden NICHT in diese Datei uebernommen
(Verfuegbarkeit != Nutzung, ZAEHLWERTE != INHALTE).

Geltende Regeln: CLAIM != EVIDENCE, UNKNOWN != PASS, keine Secrets,
keine Einschraenkung anderer, Fehler werden ehrlich als Fehler gemeldet.

## Bestand: verbundene Connector (20 laut Liste, je 1 Lese-Sonde)

Reihenfolge alphabetisch. Status der Sonde = Ergebnis des ECHTEN
Aufrufs in dieser Session (27.11.2026, UTC-Abend).

| Connector | Sonde (Funktion) | Ergebnis | Befund |
| --- | --- | --- | --- |
| amplitude | get_amplitude_context (ohne projectId) | VERBINDUNG_OK | Kontext erreichbar; Projekt-Liste nutzbar; ZAEHLWERTE hier bewusst NICHT abgebildet (Nutzungsdaten sensitiv) |
| bigquery_ | list_dataset_ids | ARG_FEHLER |projectId erforderlich, vom Betreiber nicht benannt -> UNKNOWN, kein Zugang ohne Angabe |
| cloudflare_entwicklerplattform_a480 | hyperdrive_configs_list | VERBINDUNG_OK | Server laut Angabe DEPRECATED (nutze vollstaendige API); 0 Hyperdrive-Konfigurationen |
| figma_adc4 | (keine Lese-Sonde) | NICHT_GEPRUEFT | Design-Quelle, fuer diesen Baustein ohne v91-Bezug; UNKNOWN != PASS |
| github_app | list_pull_requests / get_file_contents | VERBINDUNG_OK | Hauptarbeitsquelle; im Alltag genutzt (PR/CI/Merge-Standards) |
| gmail | list_labels | VERBINDUNG_OK | Labels lesbar (u. a. benutzerdefiniertes V91-Label vorhanden); KEIN Mailinhalt gelesen |
| google_calendar | list_calendars | VERBINDUNG_OK | 3 Kalender lesbar (Feiertage DE x2, Primaerkalender) |
| google_drive_mcp | search_files fullText 'v91' | VERBINDUNG_OK | mind. 1 V91-Bezugsdatei auffindbar (Wirkungsregister); nur Titel/ID gelesen, kein Inhalt |
| image_generation | (keine Lese-Sonde) | NICHT_GEPRUEFT | Erzeugung ist kein Lesezugriff; UNKNOWN != PASS |
| linear | list_projects | VERBINDUNG_OK | 0 Projekte sichtbar (leere Workspace) |
| mistral_mcp | list_my_connectors | VERBINDUNG_OK | Connector-Inventar erreichbar, konsistent zur Verbindungsliste |
| notion | (keine dedizierte Suchsonde) | NICHT_GEPRUEFT | Lesend verfuegbar lt. Verbindung; keine Sonde gelaufen -> UNKNOWN != PASS |
| outlook_calendar | list_calendars | VERBINDUNG_OK | Kalender des Postfachs lesbar |
| sharepoint_mcp | list_team_sites | FEHLER 401 | Lizenz ungueltig/abgelaufen -> Verbindung formal da, Zugang NEIN; Reconnect = Betreiber-Schritt |
| slack | search_channels keywords ['v91'] | VERBINDUNG_OK | 1 Treffer (#alle-in-v91); nur Kanalname/Link gelesen, KEINE Nachrichten |
| synapse_a854 | search_synapse query_term 'v91' limit 5 | VERBINDUNG_OK | Forschungsdaten-Plattform lesbar; 12 Treffer auf 'v91' (Fremddaten, nur Zaehlung uebernommen) |
| unified_search | search (Routine der Session) | VERBINDUNG_OK | Standard-Einstieg fuer fachliche Fragen, im Alltag genutzt |
| web_search | search/open_url (Routine der Session) | VERBINDUNG_OK | Standard-Einstiegel fuer oeffentliche Quellen, im Alltag genutzt |
| (Rest der Liste) | datei-/umgebungslokale Werkzeuge | VERBINDUNG_OK | Dateisystem, Bash, Sandbox: Traeger aller Lokalverifikationen |

## Nicht verbundene Connector (authentication_required)

apify, asana, atlassian, box, outlook, sharepoint_online, stripe,
teams. KEINE Aktivierung durch den Agenten erzwungen (keine
Einschraenkung anderer, keine Ermunterung zum Anbinden ohne
Betreiber-Entscheid). Zugang bleibt Betreiber-Wahl.

## Fehler ehrlich benannt

- sharepoint_mcp: 401/keine gueltige Lizenz. Weder Retry noch
  Workaround versucht. Zustand = NICHT_NUTZBAR_BIS_RECONNECT.
- bigquery_: projectId ist Pflicht-Argument und wurde nicht
  genannt. Es wurde KEIN projectId geraten (RATE != ERFAHRUNG).
- notion/figma_adc4/image_generation: keine Sonde gelaufen, also
  UNKNOWN, nicht stillschweigend als OK gebucht.

## D2-Fenster-Zwischenstand (Begleitmessung)

Seit 16:24 UTC ca. 30 neue CI-Runs, 0 Failures -> kein ROT-Ereignis
im Beobachtungsfenster. Die vorregistrierte D2-Validierung
(Macro-F1 >= 0.900 bei FN=0, ONE-SHOT) bleibt daher zurueckgestellt;
das Fenster wird NICHT auf Kosten der Vorab-registrierung verbrannt.

## Grenzen

- INVENTUR != PRUEFUNG: Eine erfolgreiche Lese-Sonde belegt nur
  Erreichbarkeit, keine Aussage ueber Datenqualitaet oder Rechte.
- Momentaufnahme einer Session; Verbindungen koennen sich aendern.
- Keine Inhalte privater Quellen (Mail, Kalender, Drive, Slack,
  Amplitude, Synapse) wurden in Repository-Dateien abgebildet.
- Veraendernde Operationen (Writes) wurden NULL durchgefuehrt.

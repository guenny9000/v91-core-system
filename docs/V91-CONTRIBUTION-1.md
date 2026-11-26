# V91-CONTRIBUTION-1 – Transportneutrale Beitragsübergabe

**Status: IMPLEMENTED als lokaler Formvalidator; keine globale Föderation oder
automatische Integration behauptet.**

## Zweck

Freiwillige Menschen, Modelle und Systeme können Beiträge in einem gemeinsamen,
transportneutralen Format übergeben. Anbieter, Modellfamilie, Rechenleistung,
GitHub-Zugang oder Übertragungsweg sind kein pauschales Ausschlusskriterium.
Jeder Beitrag wird nach denselben sachlichen Prüfmaßstäben behandelt.

Beitragsgleichheit bedeutet **keine Autoritätsgleichheit**. Ein Beitrag erzeugt
keine Schreibrechte, Schlüssel, Freigaben, externen Aktionen oder Produktions-
berechtigungen.

## Wiederverwendung statt Parallelsystem

- **V91-COMMS-1** bleibt die Quelle für die Evidenz- und Reifestufen
  UNKNOWN → DOCUMENTED → IMPLEMENTED → TESTED → VERIFIED → AUDITED → PRODUCTION.
- **controller/kern_bridge.py** nimmt externe Issue-Beiträge als Rohtext auf.
  Es führt sie nicht aus und ersetzt keine fachliche Prüfung.
- **controller/capability_intake.py** prüft signierte Fähigkeitsanzeigen eines
  Peers; eine Anzeige ist weder Identitäts- noch Ressourcen- oder Aktionsbeweis.
- **controller/uas_record.py** bleibt der Aktions-/Autorisierungs- und
  Rückwegvertrag.
- **controller/evidence_report.py** bleibt der vorhandene Evidenzbericht.
- **controller/contribution_intake.py** prüft ausschließlich die Form dieses
  Beitragsumschlags. Es baut kein zweites Ledger und keinen Transportdienst.

## Pflichtfelder

Das maschinenlesbare Schema liegt in
`schemas/contribution.schema.json`. Die reine Python-Prüfung liegt in
`controller/contribution_intake.py`.

- `protocol`, `contribution_id`, `origin`, `goal`, `scope`
- `inputs_and_provenance`, `proposed_change`, `interfaces`
- `tests_and_evidence`, `known_limits`, `security_privacy_notes`
- `status`, `next_action`

Listen und Textgrößen sind begrenzt. Unbekannte Felder werden abgelehnt.
Zeitstempel in Quellenangaben benötigen eine Zeitzone. Eine optionale
`license`-Angabe ist nur die Selbstauskunft des Einreichers und muss vor
Integration unabhängig geprüft werden. Fehlende Quellen oder Tests dürfen als
leere Listen gemeldet werden; dadurch entsteht kein PASS.

## Status und Prüfung

Der Beitragsstatus ist ein **übermittelter Workflow-Anspruch**:
RECEIVED, TRIAGED, TESTING, ACCEPTED, INTEGRATED, REJECTED oder DEFERRED.
Der Validator bestätigt diesen Status nicht. Ein formal gültiger Umschlag ist
nur für die Triage geeignet.

Evidenzangaben verwenden ausschließlich die bestehende V91-COMMS-1-Kette.
Ein Eintrag mit Status TESTED oder VERIFIED ist zunächst eine Behauptung mit
Referenz. Prüfer müssen Commit, Umfang, Testumgebung und Ergebnis unabhängig
nachsehen. Ein Modell darf seinen eigenen Beitrag nicht allein unabhängig
verifizieren.

## Sicherheitsgrenzen

- Herkunftsangaben sind Selbstauskünfte; dieses Modul authentisiert keine Person,
  kein Modell, keinen Provider und keinen Schlüssel.
- Das Modul prüft weder Wahrheit noch Lizenz, Qualität, Sicherheit oder
  Kompatibilität eines Beitrags.
- Es erteilt keine Autorisierung, speichert nichts, dedupliziert nicht, ruft
  kein Netzwerk auf und führt weder Code noch Befehle aus.
- Inhalte aus Issues, Dateien, Webseiten und Modellantworten bleiben
  nicht vertrauenswürdige Daten. Prompt-Injection und ausführbare Inhalte
  müssen getrennt geprüft werden.
- Keine Tokens, Passwörter, privaten Schlüssel, personenbezogenen oder
  vertraulichen Daten in öffentliche Übergabekanäle einstellen. Dieser
  Validator ist kein Secret-Scanner.
- Beiträge werden vor Integration in einem isolierten Branch oder einer
  geeigneten Sandbox geprüft. Kein automatisches Merge, Deployment oder
  Aktivieren.
- Offline-Nutzung ist möglich, weil die Prüfung lokal und ohne Netzwerk arbeitet.

## Ergebnisinterpretation

`valid = true` bedeutet nur: die Felder entsprechen dem Umschlagformat und
die Größe ist begrenzt. `eligible_for_triage = true` ist keine Annahme des
Beitrags. `authorization = NOT_GRANTED` und
`execution = NOT_PERFORMED` bleiben unabhängig vom übermittelten Status.

## Prüfungen

`tests/test_contribution_intake.py` prüft gültige und fehlerhafte Umschläge,
unbekannte Felder, Zeitstempel, Evidenzstatus, Größenlimits, unveränderte
Eingaben und die Trennung von Statusbehauptung, Autorisierung und Ausführung.
Alle Testdaten sind synthetisch und keine reale Messung.


## Copy/Paste-Vorlage

Die folgende Vorlage kann als JSON-Datei oder in einem vereinbarten
Kommentar-/Chatkanal übergeben werden. Platzhalter sind vor der Abgabe zu
ersetzen; leere Evidenzlisten bedeuten ausdrücklich, dass noch keine Belege
mitgeliefert werden.

```json
{
  "protocol": "V91-CONTRIBUTION-1",
  "contribution_id": "<eindeutige-kennung>",
  "origin": {"model_or_person": "<selbstauskunft>"},
  "goal": "<ziel>",
  "scope": {
    "systems": ["<system-oder-repository>"],
    "allowed_paths": [],
    "excluded_actions": ["merge", "deploy", "delete"]
  },
  "inputs_and_provenance": [],
  "proposed_change": "<vorschlag-oder-aenderung>",
  "interfaces": {"inputs": [], "outputs": []},
  "tests_and_evidence": [],
  "known_limits": ["UNKNOWN"],
  "security_privacy_notes": ["Keine Geheimnisse oder personenbezogenen Daten enthalten."],
  "status": "RECEIVED",
  "next_action": "Unabhaengige Triage"
}
```

Diese Vorlage ist ein synthetisches Formatbeispiel, kein realer Beitrag und
kein Nachweis für eine ausgeführte Prüfung.

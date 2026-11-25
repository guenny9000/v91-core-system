# Review des externen IEA-Integrationsplans (25.11.2026)

Gegenstand: der zweite, detaillierte Integrationsplan (Poll-YAML,
Adapter-Klasse, ThreadPool-Orchestrierung, Cross-Check, CI-Secrets).
Er wurde Zeile fuer Zeile gegen den seit PR #536 auf main liegenden,
regelkonformen Adapter geprueft. Diese Datei dokumentiert EHRLICH,
was uebernommen wurde, was ABGELEHNT wurde und warum
(KEINE_STILLEN_ERSETZUNGEN, KEIN_REGLBRUCH_AUS_HOEFLICHKEIT).

## UEBERNOMMEN (jetzt auf main, PR #537)

- 3.6 Cross-Check-Logik: cross_check() + cross_check_record() im
  IEA-Adapter. JEDE Quelle wird EINZELN gebucht
  (abweichungen-Dict, NICHT gemittelt), jede Divergenz landet als
  Record mit status NICHT_GEPRUEFT + fehler_status KATALOG_DIVERGENT
  in der Kette. Kongruenz wird KATALOG_KONGRUENT genannt.
- Batching: poll_batch() pollt mehrere Metriken, je Metrik GENAU EIN
  Record.
- Toleranz-Parameter fuer Rundungsunterschiede zwischen Katalogen.

## ABGELEHNT (Regelbrueche im Plan)

1. Schluessel in der URL ("?api_key=..."): verletzt die
   KEINE_SECRETS-Regel; URLs landen in Proxy-, Cron- und Fehlerlogs.
   Bereits geloest via Header (PR #536), Tests verriegeln das.
2. config/iea.yaml MIT Key im Repo: DASSelbe Problem; der Adapter
   liest NUR env IEA_API_KEY. Eine YAML-Konfig haette ohnehin nur
   Key-freie Metadaten enthalten duerfen; sie ist nicht noetig, da
   METRIK-SPECS und env bereits alleinverbindlich sind
   (NO_DUPLICATE_SYSTEMS).
3. "FAOAdapter / WHOAdapter - bereits vorhanden": FALSCH. Auf main
   existiert weder ein FAO- noch ein WHO-Adapter; die Import-Zeile
   des Plans waere sofort mit ImportError abgestuerzt. Die
   Existenz-Negativ-Sonden aus PR #536 verriegeln das.
4. Zweit-Ledger- Klasse (hashchain_ledger.py + proof_sha256 ueber
   NUR den Eintrag): kein prev_hash => keine KETTE; waere eine
   Zweite Wahrheit neben controller/ledger.py (NO_DUPLICATE).
   Bereits geloest: HashChainLedger (seq, prev_hash, Hash-Kette,
   verify_chain, fsync).
5. status "VERIFIED" bei exakter Gleichheit: ueberzueglich.
   KONGRUENZ != VERIFIZIERT: zwei Kataloge koennen gemeinsam
   falsch/gerundet sein; der Plan haette aus CLAIMs VERIFIEDs
   gemacht (CLAIM != EVIDENCE-Verstoss). Status heisst deshalb
   KATALOG_KONGRUENT mit ehrlichem Hinweis-Feld.
6. "claim == evidence fordert IDENTITAET": IEA, FAO, WHO haben
   VERSCHIEDENE Metriken (electricity_mix vs energy_consumption
   vs air_quality_co2); Namens-Gleichheit liefert fast immer
   UNKNOWN ohne Wert. Cross-Check braucht stattdessen eine
   Betreiber-METRIKBRUECKE (offen, NICHT geraten).
7. Workflows "governance_ci.yml", "v91_autonomous.yml": existieren
   NICHT. Reale Workflows: audit.yml, v91_disarmament_ci.yml,
   v91_routine_check.yml, use-policy.yml, windows-local-verify.yml.
   Ein CI-Poll-Job mit secrets.IEA_API_KEY waere ein
   BETRIEBSENTSCHEIDUNG (Netz im CI widerspricht bislang der
   Netzpolitik; NICHT ohne Freigabe gebaut).
8. Unix-int-Timestamps: das Projekt bucht ISO-UTC mit Zeitzone
   (zeitzonen-naive Werte sind fail-closed verboten).
9. ThreadPool-Parallel-Poll: IO-gebundene Katalog-Abrufe; Sequenz
   erzeugt reproduzierbare Ledger-Reihenfolge, PARALLEL waere
   Zufall ohne Mehrwert [REPRODUZIERBARKEIT > SCHNELLIGKEIT].

## Zusammenfassung

Der Plan ist als Anregung wertvoll; 3 Kernideen sind jetzt echt
auf main (Cross-Check, Toleranz, Batch-Poll). Alles Andere war
Regelbruch oder Phantom (INSTALLED/EXISTENT != BEHAUPTET). Die
Co-Pilot-Zeile des Plans bleibt: jede gelistete Datei existiert
erst, wenn sie mit Tests auf main liegt.

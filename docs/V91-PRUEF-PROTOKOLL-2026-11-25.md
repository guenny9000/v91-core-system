# V91/MAX-BEST Pruef-Protokoll (externe Abnahme-Checkliste, 25.11.2026)

Grundlage: die am 25.11.2026 vom Betreiber gelieferte Abnahme-Checkliste
fuer #521/#520/#239 und die Messdaten-Anbindung. Jede Zeile ist EHRLICH
gefuellt: PASS nur mit echtem Nachweis, NICHT_GEPRUEFT/FEHLER otherwise
(KEINE_FIKTIVEN_NACHWEISE, CHECK != INHALTSPRUEFUNG).

| Test-ID | Quelle | Erwartung | Tatsaechlich | Status | Nachweis |
|---|---|---|---|---|---|
| TF-IMP-01 | Temp-CSV (VALID) | Kennzahlen+Zaehler korrekt | gesamtnutzen BERECHNET, U=3.0 Handrechnung, bilanz.formeln=1, nicht_geprueft=0 | PASS | tests/test_max_best_datenbruecke.py::TFImp::test_tf_imp_01_valid_csv |
| TF-IMP-02 | CSV mit Luecken | NICHT_GEPRUEFT, kein 0 | QUARANTINE -> NICHT_GEPRUEFT, wert=None | PASS | test_tf_imp_02_fehlender_wert_nicht_geprueft_kein_null |
| TF-IMP-03 | p>1 / negativ | Fail-Closed | MaxBestInputError / ValueError (impact) | PASS | test_tf_imp_03_domainverletzung_fail_closed |
| TF-IMP-04 | ANNAHME-Flag | Markierung bleibt | meta.annahme=True, Zahl unveraendert, nie als MESSUNG ausgegeben | PASS | test_tf_imp_04_annahme_bleibt_gekennzeichnet |
| TF-RAD-01 | Inventar + Betreiber-ANGABEN | risiko Handrechnung | 0.3 * 150 = 45.0 MITTEL ueber ALLE Items; restrisiko NICHT_GEPRUEFT (Wirksamkeit fehlt ehrlich) | PASS | test_tf_rad_01_mit_betreiber_werten_handrechnung |
| TF-RAD-02 | Auftrag ohne Pruefwert | NICHT_GEPRUEFT | UNKNOWN -> NICHT_GEPRUEFT, kein Ersatzwert | PASS | test_tf_rad_02_ohne_pruefwert_nicht_geprueft |
| TF-RAD-03 | Ergebnistrennung | Zahlen != Flags | results/constraints/meta getrennt; constraints nur boolesche Leitplanken+Hinweis, NIE aus Zahlen abgeleitet | PASS | test_tf_rad_03_output_trennung |
| TF-ALM-01 | Wert > Schwellwert | Alarm | NICHT GEPRUEFT in diesem Lauf | NICHT_GEPRUEFT | gehoert zum OFFENEN PR #520 (emergency alert outbox); kein alerts.log-Modul auf main |
| TF-ALM-02 | Fehlender Messwert | kein Alarm | NICHT_GEPRUEFT loest keine Zahl aus (Bruecke) | PASS (nur Brueckenanteil) | test_tf_alm_02_kein_alarm_aus_nicht_geprueft |
| TF-ALM-03 | Korrupte Eingabe | Fail-Closed | NICHT GEPRUEFT als Alarm-End-to-End | NICHT_GEPRUEFT | wie TF-ALM-01 an #520 gebunden |
| IDX-OPT | Index-Strategie | Doku + CI | umgesetzt via #532 (superseded #521); Entscheidung jetzt docs/V91-INDEX-ENTSCHEIDUNG.md; CI index_lint 13/13 | PASS (mit dokumentierter Abweichung: kein archive_index.jsonl-Schema) | docs/V91-INDEX-ENTSCHEIDUNG.md, tests/test_index_lint.py |
| KEY-ROT | Schluessel-Rotation | Historie+Verifikation | NICHT DURCHGEFUEHRT | NICHT_GEPRUEFT | #239 ist ein GESCHLOSSENES Struktur-Review (Ruestungsexporte), KEIN Rotation-PR; Schluessel-Rotation ist Betreiber-Aufgabe (Witness-Tool audit/v91_rotation_witness.py auf main vorhanden) |

## Weitere Checklisten-Kriterien, ehrlich eingeordnet

- Coverage >= 95 Prozent aus coverage.xml: NICHT_GEPRUEFT - das Repo
  betreibt KEINE Coverage-Messung in CI; die Forderung wird nicht
  Shell-weise durch eine einmalige Zahl erfuellt (METRIK != NACHWEIS).
- keys/, config.yaml, signing_key: existieren in diesem Repo NICHT und
  werden fuer das Protokoll NICHT erfunden (KEINE_FIKTIVEN_NACHWEISE).
- "Merging approved" / Maintenance-Modus: bleibt BETREIBER-Entscheidung;
  kein Dashboard-Grund dafuer in diesem Lauf.
- Neue Bruecke seit diesem PR: controller/max_best_datenbruecke.py
  verkabelt impact-CSV und legacy_radar mit dem Rechner; der Rechner
  wurde NICHT veraendert (BRUECKE != ZWEITE_WAHRHEIT).

STATUS_ZUSAMMENFASSUNG: 8 PASS, 0 FAIL, 3 NICHT_GEPRUEFT (alle 3 an
offene Betreiber-/PR-Entscheidungen gebunden, NICHT vertuscht).
PROTOKOLL == MOMENTAUFNAHME != ZUSTANDSPRUEFE.

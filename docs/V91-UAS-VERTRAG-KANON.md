# V91 UAS-Vertragskanon (Issue #484)

Datum: 24.11.2026 | Status: Ehrlicher Zwischenstand, KEIN Perfektions-Status

## Zweck

Der externe UAS-Vorschlag ("THE UNIVERSAL ACTION SCHEMA", fuenfte Welle
24.11.2026) und das implementierte Record-Format
(`controller/uas_record.py`, V91CycleActionSchema 112.0.0/113.0.0)
unterscheiden sich. Issue #484 verlangt eine kanonische Quelle. Dieser
Text legt sie fest und dokumentiert den Feld-fuer-Feld-Abgleich.

## Kanonische Quelle (verbindlich)

**Alleinverbindliche Spezifikation ist der stdlib-Validator
`controller/uas_record.py`.** Es wird bewusst KEINE parallele
JSON-Schema-Datei gepflegt: zwei Texte mit Anspruch auf dieselbe
Wahrheit driften auseinander (NO_DUPLICATE_SYSTEMS,
KANON == ABLEITUNG != ZWEITE_WAHRHEIT).

Maschinenlesbar ohne zweite Wahrheit:
`python -m controller.uas_contract` gibt den Kanon als JSON aus,
abgeleitet aus den Live-Konstanten des Validators.
`python -m controller.uas_contract --check` prueft mit 10 Festsonden
echtes Validator-Verhalten gegen die deklarierten Gates (fail-closed,
Exit 1 bei Abweichung; ANZAHL_SONDE != ABDECKUNG bleibt ehrlich).

## Feld-fuer-Feld-Abgleich: externer Vorschlag vs. Implementierung

| Externer Vorschlag (V112.0.0-Text) | Implementiert als | Abweichung/Entscheid |
|---|---|---|
| Freies Aktionspaket mit Pflichtfeldern | `V91CycleActionSchema 112.0.0`, 10 Pflichtfelder (`schema_version`, `action_id`, `cycle_stage`, `hypothesis`, `pr_and_vibe`, `ci_checks`, `drift`, `follow_up_checks`, `evidence`, `unknowns`) | uebernommen, strikt fail-closed |
| Statusbehauptungen im Kopf des Berichts (perfekte Zustaende, null Fehler) | NICHT uebernommen; STATUSZEILE != EVIDENZ | bewusst verworfen |
| Implied Berechtigung durch Syntax | `authorization.auth_verified` = AUFRUFER-ANGABE (113.0.0); Gates: KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG, SYNTAX_ERTEILT_KEINE_BERECHTIGUNG | Autorisierung strikt getrennt; echte Rechte prueft nur das Zielsystem/Policy-Gate |
| Risiko-/Rollback-Angaben | `risk_level` + `rollback` (113.0.0), Gate RECOVERY_FIRST fuer HIGH/CRITICAL | uebernommen als Feld, nicht als Messung |
| Herkunft | `origin` (actor_id/actor_type/source/[timestamp_utc], 113.0.0) | uebernommen |
| Oekologie-Bereich | optionales `creation_and_life_protection` (113.0.0), je Metrik Zahl >= 0 oder UNKNOWN | uebernommen; WERT == ANGABE != MESSUNG |
| IACL-Agententransport (Agent A stuetzt sich auf Schema von Agent B) | Nur VALIDIERER umgesetzt | Netztransport NICHT VERIFIZIERT, ehrlich offen |
| Adapter V91-Core/Aurelia-Prisma/Audit-Ledger | nicht gebaut | NICHT VERIFIZIERT (nur echte E2E-Tests duerfen das aendern) |

## Migrations-/Kompatibilitaetsregeln

1. `schema_version` nur `112.0.0` oder `113.0.0`; alles andere wird
   abgelehnt (seit PR #491, vorherige Luecke geschlossen).
2. 112.0.0-Datensaetze bleiben unveraendert gueltig
   (RUECKWAERTSKOMPATIBEL).
3. 113.0.0-Felder (`origin`, `authorization`, `risk_level`, `rollback`,
   `creation_and_life_protection`) in 112.0.0-Datensaetzen sind
   UNBEKANNTE Felder und werden abgelehnt (VORWAERTS_STRENG).
4. 113.0.0 zusaetzliche Stufen: INPUT, AUTHORIZATION, EXECUTION,
   FEEDBACK; Stufen ab AUTHORIZATION verlangen
   `authorization.auth_verified == true` (Angabe, kein Recht).
5. Unbekannte Felder werden auf JEDER Ebene abgelehnt
   (additionalProperties-fail-closed).

## Zustands-/Commitment-Invarianten

- UNKNOWN != PASS, UNKNOWN_BLEIBT_UNBELEGT.
- COMMIT/LEDGER verlangen `ci_checks.overall_status == PASS` plus mind.
  einen evidence-Eintrag (EVIDENCE_BEFORE_COMMITMENT).
- Belege sind AUFRUFER-ANGABEN: der Validator verifiziert nicht gegen
  GitHub (KEIN_NETZ, METADATEN == ANGABE != BEWEIS).

## Ehrliche Grenzen (NICHT VERIFIZIERT, keine Behauptung)

- adapter_ende_zu_ende, iacl_transport, ledger_schreibpfad,
  dauerbetrieb: offen, deklariert im Kanon unter `not_verified`.
- Der Kanon ist ein Index ueber den Validator, kein Kontakt zu fremden
  Systemen (KANON != KONTAKT, KLASSIFIKATION != EINGRIFF).

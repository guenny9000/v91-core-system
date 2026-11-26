# V91 Alarm-Outbox Restore-Drill (Issue #520-Rest, 26.11.2026)

Status: SCRIPTED (CI-geprueft); kein Daemon, kein Timer, kein Netz.
Zielmodul: controller/alarm_outbox_restore_drill.py (Quellmodul: controller/alarm_outbox.py, PR #573).

## Warum dieser Drill (Issue #520-Rest)

Issue #520 fordert fuer den Alarm-Outbox neben dem Versand-Adapter
explizit einen Restore-Drill. Der Drill beantwortet die Frage:
"Was passiert semantisch, wenn v91_alarm_outbox.jsonl aus einer
Sicherung zurueckgespielt wird?" Die Antwort wird GEMESSEN, nicht
behauptet (CLAIM != EVIDENCE).

## Vertragskern (fail-closed)

- Die echte Outbox (QUELLE) wird NIE geschrieben: read-only.
- Alle Sonden laufen auf Kopien im Arbeitsverzeichnis.
- VERDICT = PASS nur wenn ALLE vier Sonden bestehen; sonst FAIL
  mit benannten Gruenden (UNKNOWN != PASS, kein 0-Ersatz).
- REUSE: create_event, record_transition, read_state, event_id_from
  aus alarm_outbox.py; KEINE zweite Parser-, Lock- oder Kette-Logik.

## Die vier Sonden

1. ZUSTANDSTREUE: Byte-Kopie wiederherstellen; je bekannter event_id
   bleibt state/retry_count identisch zur Quelle.
2. DEDUP: Das erneute Anlegen eines bekannten Ereignisses bleibt
   BEREITS_BEKANNT (kein Doppelversand-Pfad durch Restore).
3. APPEND: Die wiederhergestellte Outbox bleibt append-faehig; ein
   Uebergang haengt GENAU EINE Zeile an (append-only bleibt intakt).
4. FAIL-CLOSED: Eine mitten-in-Zeilen truncierte Kopie wird abgelehnt
   (DETECTION != BEHEBUNG; korrupte Bytes bleiben kopie-lokal erhalten,
   ISOLATE_NOT_DESTROY).

Leere Outbox (0 Events): Sonden ohne Aussage => VERDICT FAIL,
ehrlich statt Rueckseite-PASS.

## Aufruf

- Selbsttest: python3 -m controller.alarm_outbox_restore_drill --self-check
  (synthetische Fixture; SYNTHETISCH != MESSUNG)
- Echtlauf: python3 -m controller.alarm_outbox_restore_drill --outbox PFAD
  (QUELLE read-only; Exit 0 = PASS, 1 = FAIL, 2 = Nutzungsfehler)

## Ehrliche Grenzen

- DRILL != ECHTER BETRIEBS-RESTORE: file copy ohne Kompression,
  Verschluesselung oder FS-Snapshot-Verfahren.
- Betrieb auf Betreiber-Hardware: NICHT_GEPRUEFT (kein Desktop-Zugriff
  im Erstellungslauf; Lauf auf SOLAR-DESKTOP-01 bleibt Betreiber-Punkt).
- SCRIPTED != INSTALLED; kein Scheduler.
- DEAD_LETTER/CANCELLED-Ereignisse bleiben auditierbar liegen.
- Ein toter Brief bleibt tot: der Drill repariert nichts (RESTORE-DRILL
  != RECOVERY; recovery bleibt controller/ledger_recovery.py).

## Einordnung

- KEIN zweiter Outbox, kein zweites Gate, KEIN Netzwerk; die
  Versandausfuehrung bleibt deaktiviert und Betreiber-Allowlist-
  pflichtig (REQUEST != AUTHORIZATION; PLAN != VERSANDT).
- Wie alle Module: REUSE vor Neubau; dieses Dokument verweist auf die
  alleinverbindliche Modul-Dokumentation im Quellcode-Header.

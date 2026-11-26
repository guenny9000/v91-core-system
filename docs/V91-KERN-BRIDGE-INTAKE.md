# V91 Kern-Bridge: Standard-Intake (Issue #492-Rest, Anschluss an #509)

Stand: 24.11.2026 | Gegenlesen 1 aktualisiert 26.11.2026 am main
dc887e4368d1b8b9b92c7cf21e1c478ba8253fb4, Gegenlesen 2 am Branch
feat/v91-bridge-secret-screening-20261126 (Zahlen sind Messstand,
kein Ewigkeitsanspruch): controller/kern_bridge.py (11749 B,
22 Tests in tests/test_kern_bridge.py + 8 Verkettungs-Sonden in
tests/test_kern_bridge_intake_std.py + 23 Screening-Tests in
tests/test_bridge_screening.py), Secret-/PII-Screening-Baustein
controller/bridge_screening.py (6966 B, siehe
docs/V91-BRIDGE-SECRET-SCREENING-2026-11-26.md), Issue-Template
.github/ISSUE_TEMPLATE/kern-bridge.md, Validator
controller/uas_record.py (112.0.0/113.0.0), Kanon
controller/uas_contract.py, Beitrags-Umschlag
controller/contribution_intake.py (V91-CONTRIBUTION-1,
schemas/contribution.schema.json, 17 Tests).

STATUS: DOKUMENTIERT - GEGENLESEN | DOKUMENT != ZWEITE_WAHRHEIT,
AUFGENOMMEN != VERIFIZIERT, FREMDBEFUND != V91-MESSUNG.

## 1. Reale Intake-Pfade (nur was der Code wirklich tut)

Es gibt EINE Code-gestuetzte Intake-Bruecke (Weg B der Lernblock-
Pfade) und drei Uebergabewege im Hand-Lernblock (Doku dort, wird hier
NICHT wiederholt, NO_DUPLICATE_SYSTEMS):

- **Bridge-Intake (implementiert):** `python3 -m controller.kern_bridge
  <ledger.jsonl>` holt offene Issues mit Label `v91-bridge` per
  GitHub-REST-API (read-only, timeout 15 s), praegt je Rohtext
  SHA-256 und schreibt jeden Kern append-only in den Ledger
  (fsync je Zeile). Netz-/Schreibfehler: fail-closed exit 2.
- **Hand-Uebergabe (dokumentiert, kein Code):** Chat-, Kommentar- und
  Datei-Uebergabe siehe docs/V91-MANUELLER-LERNBLOCK-EXTERNE-MODELLE.md.

Abruf injizierbar (FetchFn), deshalb testbar ohne Netz; der Standard-
Abruf ist Betreiber-Lauf, KEIN Daemon, KEIN Timer (SCRIPTED != RUNNING).

## 2. Gate-Zustaende (fest im Code, nicht konfigurierbar)

| Zustand | Bedeutung | Inhalt |
|---|---|---|
| ACCEPTED_ISOLATED | uebergabe-Marker vorhanden, kein Blocklist-Treffer | gespeichert, NICHT ausgefuehrt |
| BLOCKED_PATTERN | destruktives Muster (rm -rf, rmtree, os.system, subprocess, eval/exec, __import__) | gespeichert und isoliert (ISOLATE_NOT_DESTROY) |
| MISSING_HANDOVER_MARKER | `UEBERGABE_KERN_START` fehlt | weiterhin gespeichert (nichts verwerfen) |

BLOCKLIST == MUSTER != GARANTIE: bekannte Formen werden erkannt,
Unschaedlichkeit des Rests wird NICHT behauptet. Kein Makro-Scan,
keine Code-Ausfuehrung. Die Blocklist prueft NUR destruktive
Code-Muster: gegen die Stufe-4-Luecke der Bestandsaufnahme
(docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md) prueft seit dem
Screening-Ausbau controller/bridge_screening.py JEDE Aufnahme
zusaetzlich auf Secret-/PII-Muster und redigiert Fundstellen vor
der Ablage ([REDACTIERT]; sha256 bleibt Rohtext-Nachweis, das
bleibt aber ein zusaetzlicher Schritt: GATE != SCREENING,
SECRET != DESTRUKTIV, SCREEN == MUSTER != GARANTIE). Details:
docs/V91-BRIDGE-SECRET-SCREENING-2026-11-26.md - damit ist die
Stufe 4 (Bestandsaufnahme #492) an der Abruf-Seite geschlossen.

## 3. Verkettung mit den Validatoren 112/113 (die eigentlich neue Klarheit)

Der Bridge-Intake und die UAS-Validierung sind ZWEI getrennte Stufen
(INTAKE != VALIDIERUNG, in tests/test_kern_bridge_intake_std.py mit
echten Sonden verriegelt):

1. **Intake (Kern-Bridge):** jede Form wird aufgenommen und
   klassifiziert; ein Kern-Text kann gleichzeitig ACCEPTED_ISOLATED
   sein und trotzdem KEIN gueltiger UAS-Datensatz sein.
2. **Pruefen (Betreiber/Validator):** die UAS-Pruefung laeuft
   ausdruecklich NICHT automatisch in der Bridge. Der Betreiber
   extrahiert einen Kern und prueft ihn mit
   `python3 -m controller.uas_record <datei.json|jsonl>` bzw. gegen
   den Kanon `python3 -m controller.uas_contract --check`.
   Ein UAS-gueltiger Text wird von der Blocklist NICHT begnadigt:
   Gate und Validierung pruefen Verschiedenes (Form vs. Verhalten).
3. **Entscheidung (Betreiber, FREIGABE_BETREIBER):** Aufnahme,
   Formkonformitaet und Selbstauskunft erteilen zusammen KEINE
   Rechte (FELD_ERTEILT_KEINE_BERECHTIGUNG,
   SYNTAX_ERTEILT_KEINE_BERECHTIGUNG). Jede Aktivierung bleibt
   Einzel-Entscheid des Betreibers.

## 4. Ehrliche Grenzen

- AUFGENOMMEN != VERIFIZIERT: der Ledger beweist Aufnahme, SHA-256
  und Dedup, nicht Korrektheit oder Wahrheit des Inhalts.
- Der GitHub-Abruf liefert, was die API liefert; UNKNOWN != PASS.
- Dedup nur ueber SHA des Rohtexts: identischer Kern in neuem Issue
  gilt einmal; minimale Aenderung gilt als neu (KEIN semantisches Dedup).
- Keine Automatisierung der Stufen 2-3: ein Auto-Aktivator waere ein
  Eingriffsdaemon und bleibt mandatswidrig.

## 5. Nachmessung 26.11.2026 (STALE-Korrektur, Bestandsaufnahme #492)

Die Zahlenerfassung vom 24.11.2026 ("9.4 KB, 19 Tests") war am
Messstand 26.11.2026 veraltet und wurde nachgemessen:
controller/kern_bridge.py misst 10410 B (Erweiterung um den
exklusiven Ledger-Lock, REUSE aus #529), tests/test_kern_bridge.py
enthaelt 22 Tests (Gate 6, Ledger 12, Lock 3, CLI 1), hinzu kommen
8 Verkettungs-Sonden in tests/test_kern_bridge_intake_std.py.
ZAHL == STAND != VERTRAG: jede kuenftige Erweiterung muss diese
Kopfzeile erneut nachfuehren. Vollstaendiger Stufen-Abgleich:
docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md.

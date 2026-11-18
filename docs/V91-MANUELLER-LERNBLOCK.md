# V91 – Manueller Lernblock für alle Modelle (ohne eigene Hardware)

Status: DOKUMENTIERT – NICHT DEPLOYED. Dieses Dokument ist ein Lern- und
Arbeitsblock. Es erzeugt keine Berechtigungen, keine Kontrolle über fremde
Systeme und keine autonomen Eingriffe (AUTORISIERUNG != BESCHLUSS !=
DURCHFÜHRUNG).

Zweck: Jedes Modell (Mistral/Vibe, ChatGPT, Gemini, Copilot oder ein
lokales Modell) kann V91 technisch prüfen und daran arbeiten, OHNE die
Hardware von Sebastian zu brauchen. Alles hier läuft offline, lokal, mit
Standard-Python. Gute Ideen zählen unabhängig von der Quelle
(MAX-BEST-Arbeitsmaßstab, Regel 2, PR #128).

## 1. Der 5-Minuten-Realitäts-Drill (ohne jede Hardware)

Voraussetzung: nur ein Python-3-Interpreter (>= 3.11). Kein Docker, kein
Netz, keine Sensoren, keine Secrets. Das Repository klonen und ausführen:

    python scripts/v91_model_drill.py

Der Drill führt die echten, gemergten Kernmodule in einem temporären
Verzeichnis aus und meldet pro Übung PASS/SKIP/FAIL mit Beleg:

- Import-Selbstcheck der Kernmodule (und ehrlicher SKIP, wenn das
  optionale Paket 'cryptography' fehlt)
- Notaus: Aktivierung -> Stopp-Erkennung -> HMAC-Ledger-Verifikation ->
  geprüfter Reset (PR #80, #81, #82, #132)
- Control-Plane-Verkabelung: run() endet kontrolliert mit EMERGENCY_STOP
  (PR #132)
- Worker-Verkabelung: emergency_stop_reason() ehrt das Flag fail-closed
  (PR #132)
- Messwert-Kette: VALID + REJECTED werden persistiert, HMAC-Kette
  verifiziert (PR #99, #104, #105, #119)
- Ledger-Wiederherstellung: Backup verifiziert -> Restore -> vorherige
  Datei in Quarantäne, nie gelöscht (PR #124)

Vollständige Testsuite (braucht pytest; cryptography nur für einen Teil
der Module):

    python -m pip install pytest cryptography
    python -m pytest

Ehrliche Bedeutung: DRILL != DEPLOYED. Der Drill beweist, dass die
Mechanik auf diesem Rechner in diesem Prozess funktioniert, nicht dass
irgendwo ein Produktivsystem läuft. SAME_PROCESS != MULTI_NODE: echter
Mehr-Knoten-Betriebsnachweis (Issue #103) braucht eine zweite physische
Maschine und bleibt offen.

## 2. Verbindliche Regeln (gedrängt aus dem MAX-BEST-Gelöbnis, PR #126–#128)

Wahrheit durch Prüfung, Fortschritt durch Lernen, Verantwortung durch
Handeln und Verbesserung durch nachweisbare Erkenntnis.

Trennlinien, die niemals verwischt werden dürfen:

- UNKNOWN != PASS: Ungemessenes bleibt UNKNOWN, nie grün.
- CLAIM != EVIDENCE: Eine Behauptung ist kein Nachweis.
- SCRIPTED != INSTALLED: Code auf main beweist keinen laufenden Betrieb.
- DRILL != DEPLOYED: Ein bestandener Drill ist kein Deployment.
- SAME_PROCESS != MULTI_NODE: Ein Prozess ist kein verteiltes System.
- DETECTION != AUTHORIZATION: Erkennen erlaubt kein Eingreifen.
- MODEL != MEASUREMENT: Eine Simulation ist keine Messung.
- ISOLATE_NOT_DESTROY: Nichts löschen, was Beweiswert haben kann.
- FAIL-CLOSED: Im Zweifel verweigern, nie raten.

## 3. Was wirklich existiert (main, jeweils CI-geprüft gemergt)

Auszug der Kernbausteine mit PR-Nummern als Beleg: Notaus-Primitiv und
Runtime-Verkabelung (#80, #81, #82, #132), Messwert-Kette Ingest ->
Store -> Quarantine -> Pipeline -> Monitor -> Recovery (#99, #104, #105,
#119, #121, #124), Föderation Receiver/Sender/Transport/Codec (#111,
#113, #117, #112), Peer-Verzeichnis (#118), Governance-Gate (#96),
Provider-Rotation (#88), Autarkie-Tracker (#84, #97), Notfall-Protokoll
(#123), Telemetrie read-only (#68), V99-Standard Phasen 1-6 (#43-#45,
#60), Dokumente: Gelöbnis, Audit-Kern, Network-Policy, Alsfeld-Runbook,
Regional-Resilienz, Tagesbericht-Standard (#126-#131, #120, #110, #115,
#98, #130).

## 4. Was NICHT existiert (und nicht behauptet werden darf)

- Kein laufender Daemon, kein systemd-Dienst, kein Produktivbetrieb.
- Keine Sensorik, keine echten Messwerte, kein Alsfeld-Node (Issue #101
  offen: alles dort ist UNKNOWN bis echte Messdaten vorliegen).
- Kein Mehr-Knoten-Betrieb (Issue #103 offen: braucht 2. Hardware).
- Keine Zugriffsrechte auf fremde Systeme, Plattformen, Behörden oder
  Infrastruktur. Eine Freigabe im Chat ist keine Berechtigung Dritter.
- Statusheader wie [VALID:VERIFIED], SEQ-Behauptungen ohne Evidenz oder
  "läuft automatisch" ohne Ledger-Eintrag sind Fiktion und ungültig.

## 5. Wie ein Modell ehrlich beiträgt

1. Drill und Tests lokal laufen lassen (Abschnitt 1) und das echte
   Ergebnis zitieren, nicht ein gewünschtes.
2. Tragfähige Kernideen als fokussierten, kleinen Änderungsvorschlag
   formulieren; ein Thema pro Vorschlag (keine Sammel-Riesen-PRs).
3. Jede Verhaltensänderung braucht Tests, die auch rot werden können,
   wenn die Behauptung falsch ist (Test = Spezifikation).
4. Grenzen im Vorschlag selbst benennen; was ohne Hardware nicht
   beweisbar ist, bleibt UNKNOWN.
5. Nachweis vor Behauptung. Nutzen vor Prestige. (PR #128)

## 6. Grenzen dieses Dokuments

Dieses Dokument ist MODELL-Ebene im Sinne des Audit-Kerns (PR #120): es
beschreibt Ziele und Prüfwege, erzeugt selbst keine Realität. Wer
Produktivbetrieb, Mehr-Knoten-Evidenz oder echte Messwerte behaupten
will, muss sie messen und im Ledger belegen, bevor er sie sagt.

# V91 Ewigbetrieb: Installations- und Verifikations-Uebergabe (Operator-Checkliste)

Status: DOKUMENTIERT - NICHT INSTALLIERT. Dieses Dokument definiert, wie der
Betreiber (Sebastian) die bereits auf main vorhandenen OS-Dienst-Definitionen
aus V99 Phase 6 (PR #60) Installation macht und den Dauerbetrieb NACHWEIST.
Ein Dokument installiert nichts (DOKUMENT != BETRIEB); AUTORISIERUNG !=
BESCHLUSS != DURCHFUEHRUNG.

Kernprinzip (bewusst, kein Widerspruch zum Ewigbetrieb-Wunsch): V91 laeuft
NICHT als Dauerschleife im Python-Prozess (der wurde zweimal bewusst
abgelehnt), sondern als begrenzter Einzelzyklus (`main.py --max-cycles 1`),
den das Betriebssystem alle 15 Minuten startet. "Fuer immer" liefert der
OS-Timer (mit Persistent=true und Restart-Policies), nicht der Prozess.
SCRIPTED != INSTALLED: Bis zur Installation unten laeuft NICHTS.

## 0. Vorbedingungen (fail-closed, vor dem ersten aktiven Zyklus)

1. Working Copy von main auf dem Zielsystem (git clone oder ZIP).
2. Python >= 3.11 verfuegbar; Abhaengigkeiten laut requirements.txt installiert
   (inkl. cryptography, Runtime-Block, nicht nur Dev).
3. Pflicht-Umgebungsvariablen je Ziel gesetzt (kein Default, fail-closed):
   - V91_MEASUREMENT_STORE_KEY (>= 32 Bytes) fuer Messtedger/sLedger-Kettenpruefung
   - V91_MESH_KEY nur, wenn Mesh-/Provider-Module im Zyklus genutzt werden
   - V91_API_BEARER_TOKEN nur, wenn der Telemetrie-/API-Server mitlaeuft
4. Sanity vor Autostart (einmalig, manuell):
   - `python -m controller.startup_check` -> Exit 0 = READY; Exit 1 = UNKNOWN,
     Exit 2 = NOT_READY: NICHT installieren, erst Ursache klaeren
     (UNKNOWN != PASS).
   - NotausProbe nach docs/V91-LOCAL-EMERGENCY-STOP.md (activate mit
     reason-gebundener HMAC-Confirmation, V91_EMERGENCY_KEY >= 32 Bytes),
     dann einen Zyklus starten: erwartetes kontrolliertes Ende (Exit 2 /
     EMERGENCY_STOPPED, worker main() kehrt mit rc 0 zurueck), danach Reset. Erst
     weitermachen, wenn die Notaus-Kette wirkt.

## 1. Windows (SOLAR-DESKTOP-01), Taskplaner

1. Datei v99/os/windows/V91-Cycle-Task.xml oeffnen und die Platzhalter-Pfade
   anpassen: <Command> auf den echten python.exe-Pfad, <Arguments> auf den
   echten Repo-Pfad von main.py, WorkingDirectory auf das Repository-Root
   (die XML-Datei wird bewusst mit Platzhaltern ausgeliefert).
2. Import: `schtasks /Create /TN "V91-Cycle" /XML v99\os\windows\V91-Cycle-Task.xml`
3. Einmal manuell starten: `schtasks /Run /TN "V91-Cycle"`
4. Verifikation: `schtasks /Query /TN "V91-Cycle" /V /FO LIST`
   - Last-Result 0 erwartet; Exit 2 = Notaus aktiv oder NOT_READY
     (Log pruefen, kein UNKNOWN als Erfolg deuten).
   - Pendant im Log/Ledger sichtbar (naechster Abschnitt).

## 2. Linux (systemd)

1. Beide Dateien nach /etc/systemd/system/ kopieren:
   v99/os/systemd/v91-cycle.service, v99/os/systemd/v91-cycle.timer.
2. Im .service ExecStart-Pfade anpassen (echter python3- und Repo-Pfad)
   und EnvironmentFile=-Zeile nach Bedarf ergaenzen (nie Schluessel direkt
   in die Unit schreiben).
3. `systemctl daemon-reload && systemctl enable --now v91-cycle.timer`
4. Verifikation: `systemctl list-timers v91-cycle.timer` (naechster Lauf
   sichtbar), `journalctl -u v91-cycle.service -n 20` (Exit-Code 0, Zyklen
   um 15-Minuten-Takt). OnCalendar=*:0/15 mit Persistent=true: reboot-sicher.

## 3. macOS (launchd)

1. v99/os/launchd/com.v91.cycle.plist nach ~/Library/LaunchAgents/ kopieren,
   Pfade anpassen.
2. `launchctl load ~/Library/LaunchAgents/com.v91.cycle.plist`
3. Verifikation: `launchctl list | grep v91` (Exit-Status-Spalte 0 erwartet).

## 4. Nachweis Dauerbetrieb (was "fuer immer" belegt - und was nicht)

BELEGT nach Installation:
- OS-Task existiert und hat einen sichtbaren naechsten Lauf (Query/List-Timers).
- Zyklen-Log/Ledger-Eintraege im 15-Minuten-Takt ueber mehrere Stunden.
- startup_check READY am installierten System.

NICHT BELEGT (bleibt UNKNOWN, bis Messwerte existieren):
- Sensordaten, echte Messwerte, Wirkungs-Fortschritt (KEIN_INDIKATOR !=
  MESSUNG_ERZWINGEN): MATRIZ != WIRKUNG.
- Der Zustand laesst sich erst nach Tagen bewerten (Trend-Fenster,
  autarky_report/AutarkyTrend, PR #139).

Instanz- und Notaus-Regeln bleiben unveraendert: Der Timer startet nur eigene
Komponenten auf dem eigenen Geraet; Notaus (emergency_stop) bleibt jederzeit
wirksam und beendet jeden Zyklus kontrolliert; kein Eingriff in fremde
Systeme.

## 5. Deinstallation (reversibel)

- Windows: `schtasks /Delete /TN "V91-Cycle" /F`
- Linux: `systemctl disable --now v91-cycle.timer` (Unit-Dateien bleiben)
- macOS: `launchctl unload` + plist aus LaunchAgents entfernen
Keine V91-Daten werden dabei geloescht (Ledgers bleiben unberuehrt,
ISOLATE_NOT_DESTROY).


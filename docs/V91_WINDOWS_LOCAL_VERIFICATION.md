# V91 — sicherer lokaler Prüflauf unter Windows

## Zweck und Grenze

Diese Anleitung prüft einen vorhandenen lokalen Checkout, ohne automatisch Code herunterzuladen, Pakete zu installieren, Container zu starten, Dateien zu reparieren oder einen Dienst bereitzustellen. Sie ist für einen kontrollierten ersten Test gedacht, bevor weitere Modelle oder Werkzeuge Zugriff erhalten.

## Vor dem Start

- Verwende einen eigenen Testordner, kein produktives Datenverzeichnis.
- Führe den Test nicht als Administrator aus.
- Verbinde noch keine unbekannten Modell-Plugins, Werkzeugadapter, API-Schlüssel oder persönlichen Daten.
- Prüfe, dass der Checkout aus dem erwarteten Repository stammt: `https://github.com/guenny9000/v91-core-system`.
- Wenn lokale Änderungen angezeigt werden, bewahre sie auf. Das Skript verwirft sie nicht.
- Nutze vorhandenes Python und vorhandene Testabhängigkeiten. Das Skript installiert nichts automatisch.
- Ein erfolgreicher GitHub-Testlauf beweist nicht, dass dein lokaler PC denselben Stand hat.

## Aufruf

Öffne PowerShell im lokalen Verzeichnis `v91-core-system`. Prüfe zunächst den Zustand, ohne etwas zu starten:

```powershell
git remote -v
git status --short
git rev-parse HEAD
python --version
```

Lies das Skript, bevor du es ausführst:

```powershell
Get-Content .\scripts\V91-Local-Verify.ps1
```

Wenn das Skript und der Checkout geprüft sind, führe es ohne Administratorrechte aus:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\V91-Local-Verify.ps1
```

Die Richtlinie `RemoteSigned` ist keine pauschale Sicherheitsgarantie. Ändere keine globale Ausführungsrichtlinie, nur um diesen Prüflauf zu starten. Falls die lokale Richtlinie den Aufruf blockiert, stoppe und prüfe die Ursache, statt Schutzmechanismen blind abzuschalten.

Optional, falls Docker bereits installiert ist, aber du vorerst nur Python prüfen willst:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\V91-Local-Verify.ps1 -SkipDockerComposeCheck
```

## Was das Skript tut

- protokolliert lokalen Commit, Branch und ungesicherte Änderungen;
- prüft, ob die bekannten Merge-Commits im lokalen Git-Verlauf enthalten sind;
- startet die lokalen Python-Tests und eine Syntaxkompilierung;
- prüft optional nur die Docker-Compose-Konfiguration — es startet keine Container;
- prüft das Ledger-Repository, wenn es am erwarteten Nachbarpfad liegt;
- speichert Befehle, Ergebnisse und Ausgaben in einem zeitgestempelten Verzeichnis unter `artifacts\v91-local-verify-<Zeit>`.

Das Skript ruft weder `git pull` noch `git fetch` auf. Es verändert oder repariert keine Ledger-Daten. Die Beweisprotokolle können lokale Pfade enthalten; prüfe sie, bevor du sie öffentlich teilst.

## Interpretation

- `PASS`: genau dieser lokale Prüfschritt wurde erfolgreich ausgeführt.
- `FAIL`: der Prüfschritt ist fehlgeschlagen; Ursache aus dem Log untersuchen.
- `UNKNOWN`: dieser Nachweis fehlt oder der erwartete Commit wurde im lokalen Verlauf nicht bestätigt.
- `PRODUCTION_STATUS UNKNOWN`: absichtlich. Der Prüflauf beweist keinen Produktivbetrieb, keine OS-Sandbox, keinen externen WORM-Speicher, keine vertrauenswürdige Zeit, keine echte Werkzeugfreigabe und kein Modelltraining.

## Nach dem Test

Teile zunächst nur die Zusammenfassung und die relevanten Fehlermeldungen — keine Tokens, Schlüssel, privaten Nutzdaten oder vollständigen vertraulichen Protokolle. Vor einem Netzwerkzugriff eines anderen Modells zuerst klären, welche Werkzeuge es aufrufen darf, welche Dateien es lesen kann und ob ausgehender Verkehr gesperrt ist. Unbekannte Modelle zunächst in einer getrennten Testumgebung ohne Geheimnisse, Schreibrechte oder Netzwerkzugriff betreiben.

Ein erfolgreicher Prüflauf ist ein lokaler Verifikationsnachweis, keine pauschale Sicherheitszertifizierung.

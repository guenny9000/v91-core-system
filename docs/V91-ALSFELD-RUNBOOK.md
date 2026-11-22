# V91 Alsfeld-Runbook (Issue #101)

Status: **ENTWURF – NICHT DEPLOYED.** Dieses Runbook beschreibt, was im Repository existiert und geprüft ist, und was vor Ort in Alsfeld passiert werden muss. Nichts davon läuft aktuell irgendwo im Betrieb. CLAIM != EVIDENCE, SHIPPING != INSTALLATION.

## 1. Was auf main existiert und CI-geprüft ist

| Baustein | Modul | Zweck |
|---|---|---|
| Föderations-Receiver | `controller/federation_receiver.py` | Ed25519-Peer-Identität (Membership/Revocation/Expiry), versioniertes Envelope-Schema, dauerhafter SQLite-Replay-Schutz, optionale Hash-Ketten-Quarantäne mit exakten Rohbytes |
| Transport-Bindung | `controller/federation_transport.py` | Loopback-only-UDP-Listener (Allowlist-gated), übergibt jedes Datagramm als Rohbytes an den Receiver |
| Mesh-Frame-Codec | `controller/mesh_frame_codec.py` | Gebundene, kanonische Frames (222 Bytes, HMAC-SHA256 voll, Konstantzeit) für LoRa-Klasse-Transporte; kein Funkkontakt |
| Messwertspeicher | `controller/measurement_store.py` | HMAC-Kette, fail-closed Key (`V91_MEASUREMENT_STORE_KEY` >= 32 Bytes), Lock, fsync |
| Messwert-Quarantäne | `controller/measurement_quarantine.py` | RESOLUTION als neuer Append, Originale unverändert |
| Resilienz-Monitore | `controller/resilience_monitors.py` | Futterbilanz, Aquakultur-Grenzwerte, Hygiene-Trennung (reine Bewertung übergebener Messwerte) |
| Szenario-Engine | `controller/resilience_simulation.py` | Deterministische Wochen-Simulation (Nährstoffe, getrennte Energiebilanzen, Verschleiß, Sozialkapazität); MODEL != MEASUREMENT |

## 2. Was in Alsfeld UNKNOWN bleibt (bis gemessen)

- Site-Existenz, Hardware, Strom-/Netzanschluss, LoRa-Hardware: **UNKNOWN** – hier nicht verifizierbar.
- Tierzahlen, Futterreserven, Wasserwerte, Arbeitsstunden: **UNKNOWN** – die Monitore bewerten nur übergebene Zahlen.
- Jede Aussage wie „läuft", „verifiziert", „Real-Run" für Alsfeld ist unbelegt, solange kein Messnachweis im Ledger steht.

## 3. Installationsreihenfolge vor Ort (wenn Sebastian es freigibt)

1. Rechner vorbereiten (Linux), User `v91`, Repository klonen, Abhängigkeiten (`cryptography`) installieren.
2. Schlüssel erzeugen: Ed25519-Peer-Keys für jeden Teilnehmer; `V91_MEASUREMENT_STORE_KEY` (>= 32 Bytes) und Mesh-Secrets (>= 32 Bytes) in einer geschützten Env-Datei, niemals im Repo.
3. Tests lokal laufen lassen: `python -m pytest tests/ -v` – alles muss grün sein, bevor irgendetwas startet.
4. Erst Messenger/Prozesse starten, die nur bewerten (Monitore, Szenario-Engine), dann Receiver mit Quarantäne-Ledger, zuletzt den Loopback-Listener. Kein Listener auf 0.0.0.0; die Allowlist im Transport-Modul ist bewusst fail-closed.
5. Betriebsaufzeichnung: jede Messung mit Zeitstempel und Quelle ins Ledger; Abweichungen bleiben UNKNOWN, bis sie gemessen sind.

## 4. Entscheidungs- und Sicherheitsregeln (unverändert)

- Reale Eingriffe (Knoten isolieren, Verbraucher schalten) nur nach expliziter, pro Aktion gegebener Freigabe durch Sebastian.
- UNKNOWN != PASS, DETECTION != AUTHORIZATION, ISOLATE_NOT_DESTROY.
- Kein Automatismus schaltet versorgungsrelevante Lasten; advisory-only, `executed: false`.

## 5. Offene Punkte nach diesem Runbook

- echte Multi-Node-Evidenz (Issue #103 bleibt offen bis mindestens zwei Knoten nachweisbar Envelopes austauschen),
- Futter-/Wasser-/Arbeitszeit-Basismessungen in Alsfeld, sonst bleiben alle Bewertungen UNKNOWN,
- Provider-Credential-Rotation in externen Provider-Konten (Betreiberaktion; keine offene Issue-Nummer; keine automatische Rotation durch dieses Repository).

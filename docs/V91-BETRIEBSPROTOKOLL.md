# V91-BETRIEBSPROTOKOLL (Runbook) - Forum-Claim-Ledger am Standort

V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
Regelwerk: Taskboard-Konvention #16/#138/#220, Ewigbetrieb-Doku #272.
Dieses Runbook ist ANLEITUNG, kein Ausfuehrungsnachweis. Ein Schritt
gilt erst als vollzogen, wenn sein Beweis (Report-Datei oder Ausgabe)
vorliegt. PROBE != BETRIEB, KIT != INSTALLED, SCRIPTED != ECHT.

## 1. Betriebsumgebung (SOLAR-DESKTOP-01)

- Python 3.10+ mit Paket cryptography (Ed25519-Pflicht, Ersatz nicht akzeptiert: STUB != ECHT)
- Repo-Kopie von main (V91-ARCHITEKTUR-INDEX als Versionsreferenz)
- Arbeitsverzeichnis: C:/v91/ledger/ (Ledger JSONL + Keyring = BETREIBER-KONTEXT, niemals im Repo)

## 2. Betriebsprobe (Voraussetzung fuer ALLES Weitere)

    python scripts/v91_betriebsprobe.py --report C:/v91/ledger/probe-report.json

- Exit 0 + PROBE_PASSED = Kette am Standort nachweisbar funktional
  (KEYGEN / LIFECYCLE / WATCHDOG / INTEGRITY alle PASS).
- Exit 2 + REQUIREMENTS_MISSING = ECHTES Ed25519 fehlt. KEIN Workaround
  mit Stubs oder alten Receipts; IDS-interne Tests rot tun NIEMALS ab.
- Die Report-Datei ist der Betriebsnachweis-CANDIDATE (Option --keep
  haelt das Beweisverzeichnis). Beweis archivieren, nicht ueberschreiben.

## 3. Schluessel-Erstellung (Betreiber, einmalig, offline)

    python -c "from controller.crypto_receipts import generate_signing_keypair; priv,pub=generate_signing_keypair(); print(priv.hex()); print(pub.hex())"

- Pro Identitaet (z. B. sebastian, operator) EIGENES Schluesselpaar.
- Privater Schluessel: hex64-Datei ohne Zugriffsrechte fuer Andere.
- Keyring (keyring.json): Pubkeys + expire_authorities NUR aus eigenem,
  unabhaengig vertrauenswuerdigem Kontext. NIE aus dem Ledger. NIE ins Repo.
- SIGNATURE != TRUTH: Ein Schluessel beweist Hoheit, nicht Wahrheit.

## 4. Regulaerer Sitzungszyklus (Claim-Fuehrung)

    python scripts/v91_claim_cli.py claim   --ledger ... --keyring keyring.json --key sebastian.key --author sebastian --task-id VIBE-XLIX --scope <scope> --sequence <n+1> --issued-at <epoch> --base-sha <40-SHA> --ttl-seconds 86400
    python scripts/v91_claim_cli.py done    ... (nur durch Halter)
    python scripts/v91_claim_cli.py release ... (freiwilliger Rueckzug)
    python scripts/v91_claim_cli.py status  --ledger ... --keyring keyring.json

- Exit-Codes: 0 AKZEPTIERT, 1 Eingabefehler, 2 ABGELEHNT/KONFLIKT (Datei
  unveraendert), 3 I/O/KETTE. UNKNOWN != PASS.
- Bei 2: NICHT ueberschreiben oder Datei editieren; Konflikt klaeren
  (Claim-Ledger koordiniert, #220 ist das Taskboard).

## 5. Faellige Claims behandeln (Watchdog, NUR wenn zeitlich faellig)

    python scripts/v91_watchdog.py scan   --ledger ... --keyring keyring.json         (DRY-RUN, null Byte)
    python scripts/v91_watchdog.py expire --ledger ... --keyring keyring.json --key operator.key --author operator --reason "<Pflichtbegruendung>"

- expire NUR durch expire_authority. Abgelaufen, nicht expired =
  Konflikt-gebunden bis zum expliziten EXPIRE. Kein stilles Uebernehmen.
- OPTIONALER Gate: --receipt/--policy wie im CLI (AUTHOR_CLAIM != IDENTITY).

## 6. Taskplaner-Voraussetzung (Betreiber-Entscheid)

Ein Taskplaner (z. B. Windows Aufgabenplanung: taeglicher
v91_watchdog.py scan mit Report-Option) darf erst NACH archiviertem
PROBE_PASSED-Report eingerichtet werden. Empfehlung: zuerst 3
aufeinanderfolgende manuelle Tage durchlaufen lassen, JE Report
archivieren, dann Planer mit DERSELBEN Kommandozeile.
INSTALLED != SKRIPTIERT: Der Planer selbst schreibt keinen Sonderweg
um die CLI herum.

## 7. Notfallprotokolle (aktiv, nicht optional)

### N1 - Manipulationsverdacht am Ledger
1. KEINE Schreibbefehle ausfuehren (scan liest nur).
2. Kopie des Ledger sichern (Beweis).
3. v91_claim_cli.py status und v91_watchdog.py scan laufen lassen:
   Exit 3 oder CORRUPT_OR_INVALID = Kette gebrochen/Manipulation
   nachweisbar.
4. Echtes Ledger EINFRIEREN, Ersatz-Ledger unter NEUER Datei neu
   aufbauen, Vorfall dokumentieren. Kein Zuruecksetzen ueber den Bruch.

### N2 - Schluessel-Verlust oder -Kompromittierung
1. Betroffene Identitaet sofort STILLLEGEN: aus expire_authorities
   entfernen; finale Freigabe/done durch Halter ODER restliche
   Autoritaet. BUG-BERICHTE: WICHTIG: nur Autoritaeten koennen EXPIRE;
   ein verlorener Halter-Schluessel blockiert DONE, nicht aber den
   Betrieb.
2. Neues Schluesselpaar, neue keyring (Alten SCHLUESSEL NIE loeschen
   vor Archivierung des Vorfalls).
3. Claims unter betroffener Identitaet: nicht reparieren; Konflikt
   ueber EXPIRE durch verbleibende Autoritaet loesen.

### N3 - Doppel-Claim-Lage
scan zeigt zeitlich faellig, keine Autoritaet erreichbar: KEIN manuelles
Editieren. Neu-Eintrag erst nach autorisiertem EXPIRE (Notfall:
beliebige verbleibende Autoritaet dokumentiert Grund und uebernimmt
Verantwortung).

## 8. Was dieses Runbook NICHT beweist

- KEIN Dauerbetriebsnachweis: PROBE beweist Kette am Standort am
  Probe-Tag, nicht Dauerbetrieb.
- KEIN WORM: Replace-Zugriff aufs Ledger = Macht darueber. Absicherung
  ueber Betriebssystemrechte.
- KEIN Identitaetsbeweis: SIGNATURE != TRUTH, AUTHOR_CLAIM != IDENTITY.

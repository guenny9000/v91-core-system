# V91-REPO-AUDIT-REVIEW 2026-11-26 (Pruefung eines externen Bereinigungsberichts)

Status: PRUEFBERICHT. REVIEW != FIX: Diese Datei LOESCHT NICHTS,
MERGT NICHTS und BEHEBT NICHTS. Sie prueft Behauptungen gegen
Primaerquellen. Alle gelesenen main-Staende sind vom 26.11.2026:
Aurelia-Prisma main 90a17066, V91_Agathon main 7a87635b,
v91-core-system main b1b154a8.

## 1. Provenienz

Betreiber-Uebergabe 26.11.2026: externer Bereinigungsbericht
(ChatGPT, Kanalnachweis: Session-Pruefbericht auf Issue #220
[V91-SESSION-2026-11-26-REPO-AUDIT-GPT6], Korrekturkommentare auf
Aurelia-Prisma #041 und #049, neue Issues Aurelia-Prisma #269 und
V91_Agathon #24). Regel: CLAIM != EVIDENCE - jede Behauptung wurde
einzeln gegen den Code am main geprueft.

## 2. Bestaetigung der Fremd-Markierungen (Existenz geoeffnet)

Alle fuenf vom Bericht behaupteten Aktionen EXISTIEREN:
- Aurelia-Prisma Issue #269 (10:11:45Z, offen),
- V91_Agathon Issue #24 (10:11:47Z, offen),
- Korrekturkommentar Aurelia-Prisma #041 (10:12:09Z),
- Korrekturkommentar Aurelia-Prisma #049 (10:12:11Z),
- Session-Pruefbericht auf Core Issue #220 (10:12:13Z).
Dem Bericht entsprechende Aussage "keine Dateien geloescht,
kein Merge, kein Deployment" ist konsistent mit den gelesenen
main-Staenden (kein neuer Commit auf den geprueften Pfaden).

## 3. Finding 1: Aurelia-Prisma LUX-Gate (Issue #269) - BELEGT

aurelia_prisma/core/camel_config.py: lux_check_clarity() weist
Prompts MIT weniger als 3 Zeichen zurueck; lux_gate() ist ein
Hard-Stop (nur wenn L- und U- und X-Pruefung true ergeben);
lux_check_origin()/lux_check_alignment() pruefen NUR gesetzte
Umgebungsvariablen (SYSTEM_OWNER/SYSTEM_MODE). Verdrahtung
bestaetigt: v92/supervisor.py und
aurelia_prisma/orchestrator/camel_dual_orchestrator.py rufen das
Gate. Nuance: lux_gate_detailed() existiert (Fehlergruende), die
Bewertung bleibt aber BINAER (Freigabe/Sperre), keine
Qualitaetsabstufung. Markiert als offen in #269. Umbau zur
Bewertung ist eine VERHALTENSAENDERUNG und braucht Betreiber-Go.

## 4. Finding 2: V91_Agathon Skalierung (Issue #24) - BELEGT

src/v91/multinode.py (786 B): add_node() fuegt Knoten NUR in eine
lokale Liste ein; start() und stop() werfen NotImplementedError.
tests/test_placeholders.py pins ausserdem: SemgrepIntegrator
.integrate() -> "no scan was executed",
.generate_policy() -> "no policy was generated" (src/v91/pipeline.py).
Markiert als offen in #24. KEIN blosses Entfernen der Platzhalter:
sonst entstuende eine VORGETAEUSCHTE Funktion. Der ehrliche
Platzhalter ist die richtige Form, bis echte Peers existieren.

## 5. Finding 3: Aurelia-Prisma V92 Singlefile - BELEGT
   + EIGENER ZUSATZFUND: PROVIDER-ZENTRALITAET

V92_SUPERVISOR_SINGLEFILE.py (6094 B) liegt im Root; das
modulare v92/-Paket existiert parallel; README deklariert das
Singlefile ausdruecklich als "Legacy Single-File (Referenz)";
der dokumentierte Startweg laeuft ueber python main.py (modular);
Code-Suche: KEINE Code-Referenz auf das Singlefile (nur Doku- und
Audit-Dateien); KEIN Test importiert es. Legacy-Kandidat
bestaetigt.

EIGENER ZUSATZFUND (im Fremdbericht FEHLEND): das Singlefile
verdrahtet HARDCODED https://api.openai.com und verlangt
OPENAI_API_KEY; ein lokaler Ollama-Weg FEHLT dort (camel_config
kennt USE_OLLAMA). Das beschraenkt die V91-Anbieter-Unabhaengigkeit
staerker als die GitHub-Frage: PROVIDER-ZENTRALITAET. Zudem bindet
die Datei 0.0.0.0:8000 (Netz-Exposition). Empfehlung:
verlustfreie Rotation nach legacy/ (Git-Historie bleibt), NICHT
in diesem PR ausgefuehrt; Alternativ-Startweg (main.py) ist im
README dokumentiert und geprueft.

## 6. Finding 4: Aurelia-Prisma Orchester-Log - KORREKTUR BELEGT

flowise/custom_nodes/V91_MAILBOX_LOG.node.js und der Flow
flowise/flows/V91_ORCHESTRA_DUAL_ENGINE_V1.json erzeugen/lesen
logs_v91_orchestra/. Die alte Aussage "ungenutzt/leer" ist damit
UEBERHOLT. NICHT LOESCHEN. Der Korrekturkommentar auf #049 ist
berechtigt.

## 7. Finding 5: Core GitHub-Unabhaengigkeit - BELEGT IM DESIGN,
   HARDWARE-NACHWEIS OFFEN

controller/offline_smoke.py: "zero network I/O by construction",
external_sync.gates_local_readiness = FALSE; Synchronisation ist
reines Beobachtungsfeld. docs/V91-CONTRIBUTION-1.md: transport-
neutrale Beitragsuebergabe (Issue, Datei, Copy/Paste-Vorlage,
Offline-Validator controller/contribution_intake.py, KEIN Netz).
GRENZE: Ein vollstaendiger Offline-Lauf auf der ECHTEN Hardware
des Betreibers ist NICHT_GEPRUEFT (bleibt Windows-Lock-Lauf #23).
CODE-EXISTENZ != BETRIEBSNACHWEIS.

## 8. Sicherheits- und Datenfaelle (nicht Teil dieses Reviews)

Aurelia-Prisma #239 (exponierte Zugangsdaten, Rotation) und #264
(30-MB-Lernhistorie, verlustfreie Aufteilung) bleiben OFFEN und
sind Sicherheits- bzw. Datenfaelle eigener Art: NICHT hier
"weggeraeumt", NICHT geloescht.

## 9. Ehrliche Grenzen

- REVIEW != FIX; dieser Bericht aendert KEIN Fremd-Repo.
- Code-Lektuere am main-Stand 26.11.2026; GitHub-Code-Suche
  deckt nur indizierte Dateien.
- NICHT_GEPRUEFT: echtes LUX-Gate-Verhalten im Live-Betrieb,
  Semgrep-Ergebnisse (es gibt keinen Scan), Offline-Lauf auf
  echter Hardware (#23).
- BELEGT heisst: die Behauptung stimmt mit dem gelesenen Code
  ueberein; BELEGT != GELOEST.

## 10. Reihenfolge der naechsten Schritte (jeweils Betreiber-Go)

1. Aurelia-Prisma: Singlefile-Rotation nach legacy/ (verlustfrei,
   Startwege sind geprueft: kein Code-Import, README-Referenz).
2. Aurelia-Prisma: LUX-Gate von Sperre zu BEWERTUNG umbauen
   (VERHALTENSAENDERUNG, #269).
3. Betreiber: Offline-Lauf #23 auf echter Hardware.

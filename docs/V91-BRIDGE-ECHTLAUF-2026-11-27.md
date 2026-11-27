# V91 Bridge-Echtlauf 27.11.2026: Systemechter Nachweis des Intake-Pfads

STATUS: GEMESSEN - ECHTLAUF | ABGEHOLT != GEPRUEFT, AUFGENOMMEN !=
VERIFIZIERT, SCREEN == MUSTER != GARANTIE, SCRIPTED-WERKZEUG ==
ECHT GELAUFEN (KEIN Daemon, KEIN Timer: geplanter Schritt auf
Betreiber-Go "Start real Systemecht" 27.11.2026).

## 1. Anlass und Rahmen

Vorheriger Stand: Gate, Screening-Verkabelung und Ledger waren nur
durch Unit-Tests belegt (26./27.11.2026, #582/#613/#617); ein
ECHTER Abruflauf gegen das lebende Repository war NICHT durchgefuehrt
(issues_seen 0 im Erstlauf: kein offenes Bridge-Issue vorhanden).
Der Betreiber erteilte den Go fuer einen realen Systemlauf. Dafuer
wurde die synthetische Echtlauf-Sonde #618 angelegt (Label v91-bridge,
nur dokumentierte Synthetic-Beispiele, KEINE echten Daten, KEINE
Geheimnisse) und der Betreiber-Abrufpfad real ausgefuehrt:

PYTHONPATH=. python3 -m controller.kern_bridge <ledger-pfad>

## 2. Messergebnis (zwei echte Laeufe)

Lauf 1 (Erstabruf):
- issues_seen 1, records_new 1, records_known 0
- Gate: ACCEPTED_ISOLATED 1 (Uebergabe-Marker vorhanden, kein
  destruktives Muster)
- Screening: REDACTED 1, Fundstellen email, iban_de, adresse_de
- Ablage: alle drei synthetischen Formen durch [REDACTIERT] ersetzt,
  Uebergabe-Marker im abgelegten Text erhalten

Lauf 2 (Wiederhollauf, gleiche Quelle):
- issues_seen 1, records_new 0, records_known 1
- Dedup ueber SHA-256 ECHT nachgewiesen (kein Doppel-Eintrag)

SHA-Verifikation gegen die Live-API:
- Ledger-Digest == SHA-256 ueber den ROHTEXT des Issues:
  c2f44c7e1819f54a69f3e6052b19b4ba6cec2324e04ad9dd16177dfc2d79dff3
- Der Hash bezeugt den Rohstoff, die Ablage ist redigiert
  (ABDRUCK != ABLAGE).

## 3. Reproduzierbarkeit offline

Der Screening-Teil des Echtlaufs ist offline nachrechenbar:
tests/test_bridge_echtlauf_2026_11_27.py fuehrt die dokumentierte
Sonden-Form durch screen_text und verifiziert Fundstellen-Arten,
Redaktion und Marker-Erhalt deterministisch (gleicher Text, gleiches
Ergebnis). Der Netz-Abruf selbst bleibt Betreiber-Schritt
(SCRIPTED != RUNNING, kein Daemon).

## 4. Grenzen (ehrlich)

- EIN Issue, EIN Label, EIN Repo, EIN Zeitpunkt: Momentaufnahme.
- Die Sonde enthielt bewusst NUR bekannte Muster (email, iban_de,
  adresse_de): MUSTER != GARANTIE, nicht erkannte Formen bleiben
  unredigiert abgelegt (z. B. Namen, Teiladressen).
- Gate und Screening sind KEINE Verifizierung des Inhalts.
- Der Ledger bleibt lokale append-only Ablage; er wurde NICHT ins
  Repository gepusht (keine Veraenderung am Repository).
- Die Sonde #618 ist nach dem Lauf geschlossen (completed);
  das oeffentliche Issue bleibt lesbar (Sofortregel: vor dem Posten
  pruefen wurde hier eingehalten, da nur synthetische Formen).

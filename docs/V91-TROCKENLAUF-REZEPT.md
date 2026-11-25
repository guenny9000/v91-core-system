# V91 Trockendurchlauf-Rezept (einheitliches Aufrufmuster)

Status: VERBINDLICHES REZEPT ab 25.11.2026 (PR #558); ersetzt die je
Umgebung handgebauten Lauf-Loops. Anlass: Parallel-Befund 25.11.2026,
in Umgebungen ohne installierbares pytest misslangen 72 Testmodule nur
am Import, und es gab kein einheitliches Werkzeug dafuer.

## Zwei Wege, ein Wahrheitsbegriff

1. Umgebung MIT pytest (Referenz): `pytest tests/` - bleibt die
   Referenz des CI (audit.yml). Fixtures, Parametrisierung, Plugins
   funktionieren nur hier.
2. Umgebung OHNE pytest (Sandbox, gesperrte Paketinstallation):
   `python3 -m controller.trockenlauf --tests-dir tests --repo-root .`
   Selbsttest des Runners: `python3 -m controller.trockenlauf --self-check`

## Drei-Klassen-Verdict des Runners (KEINE zwei Klassen)

- PASS: alle Tests des Moduls gruen.
- FAIL: echter Bestandsfehler (Assertion/Exception im Test) ODER ein
  Testmodul ohne einen einzigen lauffaehigen Test (leer = verdaechtig).
- ENV_FEHLT: ImportError BEVOR irgendein Test lief (z.B. pytest oder
  cryptography fehlt). Das ist eine Umgebungsgrenze, KEIN Bestandsfehler
  (UNKNOWN != ROT) - wird einzeln mit Grund gemeldet, verhindert aber
  KEIN exit 0.

Exit-Codes: 0 = kein FAIL (ENV_FEHLT erlaubt), 1 = mindestens ein FAIL,
5 = Testverzeichnis fehlt.

## Ehrliche Grenzen

- Der Runner ersetzt pytest NICHT: Fixture-Funktionen und importierte
  pytest-Abhaengigkeiten werden klassifiziert, nicht simuliert.
- EIN lokaler Lauf (welcher Weg auch immer) ist KEINE CI-Evidenz:
  CI bleibt die Pipeline auf GitHub (audit/disarmament/governance).
  LOCAL != CI, SCRIPTED != INSTALLED.
- pytest-Import in einem Modul bedeutet NICHT automatisch ENV_FEHLT:
  nur wenn das Paket WIRKLICH fehlt (ImportError vor Testlauf).

## Empfohlene Reihenfolge eines Trockendurchlaufs

1. `python3 -m py_compile controller/*.py` (Kompilierbarkeit)
2. `python3 -m controller.trockenlauf --self-check`
3. Runner ueber `tests/` (oder pytest, wenn vorhanden)
4. `python3 -m controller.fiction_scan --path .` und
   `python3 -m controller.secret_scan --path .`
5. Die ENV_FEHLT-Liste dokumentieren, NICHT als Bestandsfehler
   ausweisen, und den CI-Stand (PR + Merge-SHA) dazuschreiben,
   damit klar ist, WAS der Lauf gemessen hat.

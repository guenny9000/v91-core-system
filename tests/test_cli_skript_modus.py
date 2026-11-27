"""Regressionstests: CLI-Skript-Modus (#460-Schatten, Reparatur 27.11.2026).

Vier Controller-Module brachen beim DIREKTEN Skript-Aufruf
(``python3 controller/<modul>.py --help``): Im Skript-Modus steht der
controller-Ordner selbst auf sys.path, und dann schattet die Datei
controller/controller.py das Namespace-Paket 'controller' - jeder
ungesicherte ``from controller.X import``-Import schlaegt fehl
(ModuleNotFoundError: 'controller' is not a package). Die CI sieht das
nicht, weil sie immer ab der Wurzel als Paket importiert. Diese Tests
rufen die CLIs deshalb bewusst ALS SKRIPT per subprocess auf.

Reparatur-Muster (wie workload_norm.py): Skript-Ordner idempotent aus
sys.path entfernen, ROOT einfuegen - und zwar VOR dem ersten
controller-Import (mess_pilot trug den Block urspruenglich NACH dem
Import).
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]

# Alle vier Module hatten den #460-Schatten (27.11.2026 empirisch belegt:
# Traceback bei --help vor der Reparatur, ok danach).
SKRIPT_MODUS_MODULE = (
    "host_metrics",
    "mess_pilot",
    "review_index",
    "offline_smoke",
)


def _lauf(argumente, timeout=120):
    return subprocess.run(
        [sys.executable, *argumente],
        capture_output=True, text=True, timeout=timeout,
    )


class SkriptModusHilfeTest(unittest.TestCase):
    """--help laeuft nur, wenn die Imports im Skript-Modus ueberstehen."""

    def test_help_ohne_traceback_je_modul(self):
        for name in SKRIPT_MODUS_MODULE:
            mit_sich = self.subTest(modul=name)
            with mit_sich:
                prozess = _lauf([
                    str(REPO / "controller" / (name + ".py")), "--help"
                ])
                self.assertEqual(
                    prozess.returncode, 0,
                    name + ": STDERR=" + prozess.stderr[:400],
                )
                self.assertNotIn("Traceback", prozess.stderr)
                self.assertNotIn("ModuleNotFoundError", prozess.stderr)
                # argparse-Hilfe beweist, dass der Parser erreichtet wurde.
                self.assertIn("usage:", prozess.stdout.lower())


class OfflineSmokeSkriptE2ETest(unittest.TestCase):
    """Echter Skript-Modus-Lauf ohne Netz: SMOKE_UNKNOWN bleibt ehrlich."""

    def test_lauf_ohne_flag_mit_fehlendem_ledger_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag = pathlib.Path(tmp) / "stopped.flag"  # nicht angelegt
            fehlt = pathlib.Path(tmp) / "gibt-es-nicht.jsonl"
            prozess = _lauf([
                str(REPO / "controller" / "offline_smoke.py"),
                "--flag-path", str(flag),
                "--ledger", "main=" + str(fehlt),
                "--sync-status", "OK",
            ])
            # Fehlende Ledger-Datei ist KEIN FAIL, sondern UNKNOWN
            # (UNKNOWN != PASS, NO_DATA_AVAILABLE != PASS).
            self.assertEqual(prozess.returncode, 1, prozess.stdout[-300:])
            self.assertIn("SMOKE_UNKNOWN", prozess.stdout)
            self.assertNotIn("Traceback", prozess.stderr)
            # Sync ist reines Beobachtungsfeld, nie Ready-Kriterium.
            self.assertIn('"external_sync"', prozess.stdout)
            self.assertIn('"gates_local_readiness": false', prozess.stdout)
            self.assertIn('"status": "OK"', prozess.stdout)


if __name__ == "__main__":
    unittest.main()

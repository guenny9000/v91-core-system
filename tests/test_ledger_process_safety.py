"""
Tests fuer die Interprozess-Sicherheit des HashChainLedger
(controller/ledger.py, Haertung 25.11.2026).

Anlass (Fremdbefund-Nachmessung P0): HashChainLedger nutzte nur
threading.Lock; der vorhandene Baustein controller/ledger_lock.py
wurde nicht verwendet. Zwei PROZESSE haetten mit veraltetem
prev_hash schreiben koennen (Kette kaputt).

Pins:
- ZWEI ECHTE PROZESSE (kein Thread, kein Mock) jede N appends auf
  DASSELBE Ledger -> verify_chain danach sauber, seq lueckenlos 0..2N-1.
- Stale-Kopf-Sonde: Prozess B laedt den Kopf VOR A's appends und
  haengt DANACH an -> der neue Record verketet gegen den ECHTEN
  Datei-Kopf (Neuabgleich im kritischen Abschnitt), nicht gegen den
  In-Memory-Stand.
- LOCK != BEWEIS: die Sonden zeigen Korrektheit unter Last, sie
  beweisen nicht, dass jede ungeschuetzte Race immer fehlschlaegt.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller.ledger import GENESIS, HashChainLedger, verify_chain

CHILD = r"""
import sys
sys.path.insert(0, {repo!r})
from controller.ledger import HashChainLedger

path = sys.argv[1]
mode = sys.argv[2]
count = int(sys.argv[3])
ledger = HashChainLedger(path)
if mode == "hold":
    # Kopf VOR fremden appends laden (Stale-Sonde), dann anhaengen.
    head_before = ledger.head
    import time; time.sleep(1.2)
    for i in range(count):
        rec = ledger.append({{"kind": "stale", "i": i}}, "2026-11-25T00:00:00Z")
    assert rec["prev_hash"] != head_before or head_before == "0" * 64, (
        "anhaengte gegen ALTEN Kopf: " + head_before)
else:
    for i in range(count):
        ledger.append({{"kind": mode, "i": i}}, "2026-11-25T00:00:00Z")
"""


class LedgerProcessSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "ledger.jsonl")

    def tearDown(self) -> None:
        self._tmp.cleanup()
        for suffix in ("", ".lock"):
            lockish = Path(self.path + suffix)
            if lockish.exists():
                lockish.unlink()

    def _child(self, mode: str, count: int) -> subprocess.CompletedProcess:
        repo = str(pathlib.Path(__file__).resolve().parents[1])
        return subprocess.run(
            [sys.executable, "-c", CHILD.format(repo=repo),
             self.path, mode, str(count)],
            capture_output=True, text=True, timeout=120)

    def test_two_processes_one_ledger_chain_stays_valid(self):
        procs = [subprocess.Popen(
            [sys.executable, "-c", CHILD.format(
                repo=str(pathlib.Path(__file__).resolve().parents[1])),
             self.path, "p%d" % n, "5"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(2)]
        for p in procs:
            out, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode("utf-8", "replace"))
        report = verify_chain(self.path)
        self.assertEqual(report["records_checked"], 10)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["chain_valid"])
        with open(self.path, encoding="utf-8") as fh:
            seqs = [json.loads(line)["seq"] for line in fh if line.strip()]
        self.assertEqual(sorted(seqs), list(range(10)))

    def test_stale_head_cannot_break_chain_after_resync(self):
        # Prozess B haelt einen ALTEN Kopf, waehrend A anhaengt;
        # B's append muss gegen den NEUEN Datei-Kopf verketten.
        repo = str(pathlib.Path(__file__).resolve().parents[1])
        holder = subprocess.Popen(
            [sys.executable, "-c", CHILD.format(repo=repo),
             self.path, "hold", "2"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import time
        time.sleep(0.3)
        self._child("writer", 2)
        out, err = holder.communicate(timeout=120)
        self.assertEqual(holder.returncode, 0, err.decode("utf-8", "replace"))
        report = verify_chain(self.path)
        self.assertEqual(report["records_checked"], 4)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["chain_valid"])

    def test_lock_file_is_companion_not_ledger(self):
        from controller.ledger_lock import ledger_lock_path
        HashChainLedger(self.path).append({"k": 1}, "2026-11-25T00:00:00Z")
        lock = ledger_lock_path(Path(self.path))
        self.assertTrue(lock.exists())
        self.assertNotEqual(lock, Path(self.path))
        report = verify_chain(self.path)
        self.assertEqual(report["records_checked"], 1)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()

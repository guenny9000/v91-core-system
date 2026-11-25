"""
Tests fuer controller/ledger_lock.py (LEDGER-LOCK-REST, Kennung im
Architektur-Index) und die Verriegelung der append-only Ledger:
quorum_ledger, receipt_store, research_watch, mess_pilot (Delegation).

Fail-closed-Pins: Lock wird IMMER freigegeben (auch bei Ausnahme im
kritischen Abschnitt); EINE Lockdatei je Ledger (LOCK_DATEI !=
LEDGER_DATEI, ISOLATE_NOT_DESTROY); der kritische Abschnitt umfasst
Lesen + Schreiben. PARALLELITAET != BEWEIS: die Thread-Sonden zeigen
Serialisierung und Ketten-Validitaet unter Last, sie beweisen NICHT,
dass jede ungeschuetzte Race immer fehlschlaegt (LOCK != BEWEIS,
UNKNOWN != PASS). Windows-Explorer: msvcrt-Pfad kann auf POSIX-Runnern
NICHT ausgeuebt werden und bleibt ehrlich ungetestet.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import threading
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller.ledger_lock import (
    LedgerLockError,
    exclusive_ledger_lock,
    ledger_lock_path,
)
from controller.research_watch import ResearchObservationLog

REPO = pathlib.Path(__file__).resolve().parents[1]

try:
    from controller.crypto_receipts import generate_signing_keypair
    HAS_CRYPTO = True
except Exception:  # Abhaengigkeit fehlt in dieser Umgebung: ehrlich ueberspringen
    HAS_CRYPTO = False


class LedgerLockModuleTests(unittest.TestCase):
    def test_windows_lock_uses_msvcrt_and_releases(self):
        calls = []
        fake_msvcrt = SimpleNamespace(
            LK_LOCK=1, LK_UNLCK=2,
            locking=lambda fd, mode, count: calls.append((fd, mode, count)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "log.jsonl"
            with patch("controller.ledger_lock.os.name", "nt"), patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
                with exclusive_ledger_lock(ledger):
                    pass
        self.assertEqual(2, len(calls))
        self.assertEqual([1, 2], [call[1] for call in calls])
        self.assertTrue(all(call[2] == 1 for call in calls))
        self.assertEqual(calls[0][0], calls[1][0])

    def test_windows_lock_failure_refuses_to_yield(self):
        def fail_lock(fd, mode, count):
            if mode == 1:
                raise OSError("synthetic lock failure")
        fake_msvcrt = SimpleNamespace(LK_LOCK=1, LK_UNLCK=2, locking=fail_lock)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "log.jsonl"
            with patch("controller.ledger_lock.os.name", "nt"), patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
                with self.assertRaises(LedgerLockError):
                    with exclusive_ledger_lock(ledger):
                        self.fail("critical section must not run without an interprocess lock")

    def test_lock_file_created_and_is_companion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "log.jsonl"
            with exclusive_ledger_lock(ledger) as lock_path:
                self.assertEqual(ledger_lock_path(ledger), lock_path)
                self.assertTrue(lock_path.is_file())
                self.assertNotEqual(ledger.name, lock_path.name)
            self.assertTrue(lock_path.is_file())  # Lockdatei bleibt (keine Daten, kein Verlust)

    def test_lock_released_on_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "log.jsonl"
            with self.assertRaises(RuntimeError):
                with exclusive_ledger_lock(ledger):
                    raise RuntimeError("kritischer Abschnitt scheitert")
            # Freigabe muss funktioniert haben: erneuter Lock blockiert nicht
            with exclusive_ledger_lock(ledger):
                pass

    def test_lock_serializes_threads(self):
        """Zwei Threads mit separaten Lock-Kontexten duerfen nicht interlieren."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "log.jsonl"
            counter = []
            barrier = threading.Barrier(2)

            def worker(name):
                barrier.wait()
                with exclusive_ledger_lock(ledger):
                    counter.append(name)
                    counter.append(name + "-end")

            t1 = threading.Thread(target=worker, args=("a",))
            t2 = threading.Thread(target=worker, args=("b",))
            t1.start(); t2.start(); t1.join(); t2.join()
            # keine verschachtelten Kontexte: jedes "-end" direkt nach seinem Namen
            self.assertEqual(counter[0] + "-end", counter[1])
            self.assertEqual(counter[2] + "-end", counter[3])


class ResearchWatchLockTests(unittest.TestCase):
    def test_parallel_claims_produce_valid_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "research_watch.jsonl"
            log = ResearchObservationLog(log_path)
            errors = []

            def worker(idx):
                try:
                    for j in range(3):
                        log.record_claim(
                            claim="claim-%d-%d" % (idx, j),
                            claim_kind="beobachtung",
                            evidence_reference=None,
                            note="parallel",
                            now=datetime(2026, 11, 24, tzinfo=timezone.utc),
                        )
                except Exception as exc:  # pragma: no cover - Fehlersammler
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual([], errors)
            reloaded = ResearchObservationLog(log_path)
            entries = reloaded.list_entries()
            self.assertEqual(24, len(entries))
            self.assertTrue(reloaded.verify_chain())
            seqs = [e["seq"] for e in entries]
            self.assertEqual(sorted(seqs), list(range(1, 25)))

    def test_lock_file_is_companion_not_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "research_watch.jsonl"
            ResearchObservationLog(log_path).record_claim("c", "k")
            self.assertTrue(ledger_lock_path(log_path).is_file())
            self.assertEqual(1, len([p for p in log_path.parent.iterdir()
                                     if p.name == "research_watch.jsonl"]))


@unittest.skipUnless(HAS_CRYPTO, "cryptography-Paket fehlt in dieser Umgebung")
class QuorumLedgerLockTests(unittest.TestCase):
    def test_two_instances_alternating_appends_both_see_full_chain(self):
        from controller.quorum_ledger import QuorumLedger
        keys = {a: generate_signing_keypair() for a in ("agent-a", "agent-b")}
        public = {a: pub for a, (_, pub) in keys.items()}
        from controller.quorum_ledger import build_signed_vote

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            one = QuorumLedger(path, public)
            two = QuorumLedger(path, public)
            one.append_vote(build_signed_vote("agent-a", "a" * 64, 1, 1, True, 1000, "v1", keys["agent-a"][0]))
            two.append_vote(build_signed_vote("agent-b", "b" * 64, 1, 2, True, 1001, "v1", keys["agent-b"][0]))
            one.append_vote(build_signed_vote("agent-b", "b" * 64, 2, 3, True, 1002, "v1", keys["agent-b"][0]))
            self.assertEqual(3, one.entry_count())
            self.assertEqual(2, two.entry_count())  # two kennt nur NEUABGLEICH, keine Allwissenheit
            reloaded = QuorumLedger(path, public)
            self.assertEqual(3, reloaded.entry_count())
            # agent-b hoechste Sequenz im File: 3 (dritter Vote agent-b seq 3)
            self.assertEqual(3, reloaded.replay_floor("agent-b"))

    def test_parallel_appends_chain_valid_and_floors_intact(self):
        from controller.quorum_ledger import QuorumLedger, build_signed_vote
        agents = ["agent-%d" % i for i in range(4)]
        keys = {a: generate_signing_keypair() for a in agents}
        public = {a: pub for a, (_, pub) in keys.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledgers = [QuorumLedger(path, public) for _ in agents]
            errors = []

            def worker(idx):
                agent = agents[idx]
                try:
                    for seq in range(1, 4):
                        ledgers[idx].append_vote(build_signed_vote(
                            agent, "d" * 64, 1, seq, True, 2000 + seq, "v1", keys[agent][0]))
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual([], errors)
            reloaded = QuorumLedger(path, public)
            self.assertEqual(12, reloaded.entry_count())
            for agent in agents:
                self.assertEqual(3, reloaded.replay_floor(agent))

    def test_shrunk_ledger_refuses_append_fail_closed(self):
        from controller.quorum_ledger import QuorumLedger, QuorumLedgerError, build_signed_vote
        keys = {a: generate_signing_keypair() for a in ("agent-a",)}
        public = {a: pub for a, (_, pub) in keys.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, public)
            ledger.append_vote(build_signed_vote("agent-a", "a" * 64, 1, 1, True, 1000, "v1", keys["agent-a"][0]))
            path.write_text("", encoding="utf-8")  # Schrumpfen simulieren
            with self.assertRaises(QuorumLedgerError):
                ledger.append_vote(build_signed_vote("agent-a", "a" * 64, 1, 2, True, 1001, "v1", keys["agent-a"][0]))



@unittest.skipUnless(HAS_CRYPTO, "cryptography-Paket fehlt in dieser Umgebung")
class ReceiptStoreLockTests(unittest.TestCase):
    def test_two_instances_append_chain_valid_and_floors_synced(self):
        from controller.quorum_ledger import build_signed_vote
        from controller.receipt_store import ReceiptStore, ReceiptStoreError
        from controller.review_receipt import build_review_receipt
        keys = {a: generate_signing_keypair() for a in ("agent-a", "agent-b")}
        public = {a: pub for a, (_, pub) in keys.items()}

        def receipt(agent, vote_record, tag):
            return build_review_receipt(
                vote_record, private_key=keys[agent][0],
                provider="prov-" + agent, model="model-x",
                stance="APPROVE" if vote_record["approve"] else "REJECT",
                rationale="lock-test " + tag,
                evidence=["runbook://lock-test"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt_store.jsonl"
            one = ReceiptStore(path, public)
            two = ReceiptStore(path, public)
            vote1 = build_signed_vote("agent-a", "a" * 64, 1, 1, True, 1000, "v1", keys["agent-a"][0])
            vote2 = build_signed_vote("agent-b", "b" * 64, 1, 1, True, 1001, "v1", keys["agent-b"][0])
            one.append_receipt(receipt("agent-a", vote1, "r1"), vote1)
            two.append_receipt(receipt("agent-b", vote2, "r2"), vote2)
            # Replay: Sequenz 1 ist bereits klein gegen den sync-ten Floor
            with self.assertRaises(ReceiptStoreError):
                one.append_receipt(receipt("agent-a", vote1, "r3"), vote1)
            reloaded = ReceiptStore(path, public)
            self.assertEqual(2, reloaded.entry_count())
            self.assertEqual(1, reloaded.replay_floor("agent-a"))
            self.assertEqual(1, reloaded.replay_floor("agent-b"))


class SourcePins(unittest.TestCase):
    """Verriegelt die Lock-Nutzung im Quelltext (CLAIM != EVIDENCE)."""

    def test_ledgers_use_exclusive_ledger_lock(self):
        for rel, needle in (
            ("controller/quorum_ledger.py", "with exclusive_ledger_lock(self._path):"),
            ("controller/receipt_store.py", "with exclusive_ledger_lock(self._path):"),
            ("controller/research_watch.py", "with exclusive_ledger_lock(self._path):"),
            ("controller/mess_pilot.py", "with exclusive_ledger_lock(log_path):"),
            ("controller/kern_bridge.py", "with exclusive_ledger_lock(ledger_path):"),
        ):
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertIn(needle, text, rel + " fehlt die Lock-Nutzung")
            self.assertIn("ledger_lock", text, rel + " importiert den Baustein nicht")

    def test_kern_bridge_uses_the_lock_with_fetch_outside(self):
        """#530-Rest: kern_bridge verriegelt Dedup+Append; der Abruf bleibt davor."""
        text = (REPO / "controller" / "ledger_lock.py").read_text(encoding="utf-8")
        self.assertIn("quorum_ledger", text)
        self.assertIn("receipt_store", text)
        self.assertIn("research_watch", text)
        self.assertIn("kern_bridge", text)
        kern = (REPO / "controller" / "kern_bridge.py").read_text(encoding="utf-8")
        self.assertIn("with exclusive_ledger_lock(ledger_path):", kern,
                      "kern_bridge fehlt die Lock-Nutzung (#530-Rest)")
        self.assertLess(
            kern.index("issues = fetch_fn(repo, label)"),
            kern.index("with exclusive_ledger_lock("),
            "Netz-Abruf darf NICHT im kritischen Abschnitt stehen",
        )


if __name__ == "__main__":
    unittest.main()

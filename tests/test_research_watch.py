"""
Tests fuer controller.research_watch: hash-verkettetes Claim-Log,
Evidenzpflicht, Manipulationserkennung, fail-closed.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller.research_watch import (
    ResearchObservationLog,
    ResearchWatchError,
)


def _now(tag: str):
    return datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)


class ResearchWatchTests(unittest.TestCase):

    def _log(self, root: Path) -> ResearchObservationLog:
        return ResearchObservationLog(root / "research_watch.jsonl")

    def test_first_and_second_entry_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            first = log.record_claim("Studie X meldet Effekt", "studie", "doi:10.0000/x", "", _now("a"))
            second = log.record_claim("Studie Y", "studie", "https://example.org/y", "", _now("b"))
            self.assertEqual(1, first["seq"])
            self.assertEqual(2, second["seq"])
            self.assertEqual(first["entry_hash"], second["prev_hash"])
            self.assertTrue(log.verified())

    def test_claim_without_evidence_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            record = log.record_claim("Gerücht Z", "geruecht", None, "nur Mundpropaganda", _now("a"))
            self.assertEqual("UNKNOWN", record["status"])
            self.assertEqual(1, len(log.open_claims()))
            self.assertEqual(0, len([e for e in log.list_entries() if e["status"] == "BELEGT_EINSCHAETZUNG"]))

    def test_claim_with_evidence_is_belegt_einschaetzung(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            record = log.record_claim("Meta-Analyse", "studie", "doi:10.0000/m", "", _now("a"))
            self.assertEqual("BELEGT_EINSCHAETZUNG", record["status"])
            self.assertEqual(0, len(log.open_claims()))

    def test_invalid_evidence_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            with self.assertRaises(ResearchWatchError):
                log.record_claim("Claim", "studie", "einfach so behauptet", "", _now("a"))

    def test_empty_claim_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            with self.assertRaises(ResearchWatchError):
                log.record_claim("  ", "studie", "doi:10.0000/x", "", _now("a"))
            with self.assertRaises(ResearchWatchError):
                log.record_claim("ok", "  ", None, "", _now("a"))
            with self.assertRaises(ResearchWatchError):
                log.record_claim("ok", "studie", None, None, _now("a"))

    def test_tampering_detected_and_append_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_watch.jsonl"
            log = ResearchObservationLog(path)
            log.record_claim("Claim A", "studie", "doi:10.0000/a", "", _now("a"))
            lines = path.read_text(encoding="utf-8").splitlines()
            entry = json.loads(lines[0])
            entry["claim"] = "gefaelschter Claim"
            path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
            log2 = ResearchObservationLog(path)
            self.assertFalse(log2.verified())
            with self.assertRaisesRegex(ResearchWatchError, "append refused"):
                log2.record_claim("Claim B", "studie", "doi:10.0000/b", "", _now("b"))

    def test_corrupt_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_watch.jsonl"
            path.write_text("kein json\n", encoding="utf-8")
            with self.assertRaises(ResearchWatchError):
                ResearchObservationLog(path).list_entries()

    def test_unterminated_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_watch.jsonl"
            path.write_text('{"seq": 1}', encoding="utf-8")
            with self.assertRaises(ResearchWatchError):
                ResearchObservationLog(path).list_entries()

    def test_blank_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_watch.jsonl"
            path.write_text('{"seq": 1, "entry_hash": "x"}\n\n', encoding="utf-8")
            with self.assertRaises(ResearchWatchError):
                ResearchObservationLog(path).list_entries()

    def test_reload_continues_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_watch.jsonl"
            log = ResearchObservationLog(path)
            log.record_claim("Claim A", "studie", "doi:10.0000/a", "", _now("a"))
            log2 = ResearchObservationLog(path)
            second = log2.record_claim("Claim B", "studie", "doi:10.0000/b", "", _now("b"))
            self.assertEqual(2, second["seq"])
            self.assertTrue(log2.verified())

    def test_non_path_fails_closed(self):
        with self.assertRaises(ResearchWatchError):
            ResearchObservationLog("kein-pfad")

    def test_ledger_and_path_references_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(Path(tmp))
            log.record_claim("Ledger-Fund", "beobachtung", "ledger::seq-42", "", _now("a"))
            log.record_claim("Lokal-Fund", "beobachtung", "/daten/studie.pdf", "", _now("b"))
            self.assertEqual(2, len(log.list_entries()))
            self.assertEqual(0, len(log.open_claims()))


if __name__ == "__main__":
    unittest.main()

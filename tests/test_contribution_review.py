"""Tests fuer das Contribution-Review-Journal (Issue #492, Stufe-6-Rest).

Verriegelt: Kettenregel ab RECEIVED, Uebergangsmatrix, Selbstfreigabe-
Sperre, Journal-Integritaet fail-closed, REUSE des Umschlag-Validators,
keine Rechte, kein Vollzug. REVIEW_JOURNAL != FREIGABE.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import contribution_intake  # noqa: E402
from controller import contribution_review as cr  # noqa: E402


def _envelope() -> dict:
    """Gueltiger V91-CONTRIBUTION-1-Umschlag (Validator-bestaetigt)."""
    envelope = {
        "protocol": "V91-CONTRIBUTION-1",
        "contribution_id": "contrib-2026-11-27-001",
        "origin": {"model_or_person": "Fremdes Modell A"},
        "goal": "Luecke in der Rueckmeldung von Beitragsentscheidungen schliessen",
        "scope": {"systems": ["v91-core-system"]},
        "inputs_and_provenance": [],
        "proposed_change": "Review-Journal als Werkzeug fuer den Betreiber",
        "interfaces": {"inputs": ["envelope-json"], "outputs": ["journal-jsonl"]},
        "tests_and_evidence": [],
        "known_limits": ["keine Identitaetspruefung"],
        "security_privacy_notes": ["keine vertraulichen Inhalte"],
        "status": "RECEIVED",
        "next_action": "TRIAGE",
    }
    valid, errors = contribution_intake.validate_contribution(envelope)
    assert valid, errors
    return envelope


class RecordReviewTest(unittest.TestCase):
    def test_first_entry_starts_from_received(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            entry = cr.record_review(
                _envelope(), journal, "TRIAGED",
                "Struktur geprueft, zur Pruefung vorgemerkt", "Betreiber",
                recorded_at="2026-11-27T15:00:00+00:00",
            )
            self.assertEqual(entry["from_status"], "RECEIVED")
            self.assertEqual(entry["to_status"], "TRIAGED")
            chains = cr.load_journal(journal)
            self.assertEqual(len(chains), 1)
            self.assertEqual(len(chains["contrib-2026-11-27-001"]), 1)

    def test_full_chain_to_integrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            envelope = _envelope()
            for to_status, begruendung in (
                ("TRIAGED", "triagiert"),
                ("TESTING", "im Test"),
                ("ACCEPTED", "unabhaengig geprueft und angenommen"),
                ("INTEGRATED", "via PR gemergt"),
            ):
                cr.record_review(
                    envelope, journal, to_status, begruendung, "Betreiber",
                    recorded_at="2026-11-27T15:00:00+00:00",
                )
            chain = cr.load_journal(journal)["contrib-2026-11-27-001"]
            self.assertEqual(
                [e["to_status"] for e in chain],
                ["TRIAGED", "TESTING", "ACCEPTED", "INTEGRATED"],
            )

    def test_invalid_transition_blocked_and_journal_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            with self.assertRaises(cr.ReviewBlockedError):
                cr.record_review(
                    _envelope(), journal, "ACCEPTED", "Sprung", "Betreiber",
                    recorded_at="2026-11-27T15:00:00+00:00",
                )
            self.assertFalse(journal.exists())
            self.assertEqual(cr.load_journal(journal), {})

    def test_terminal_states_are_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            envelope = _envelope()
            cr.record_review(
                envelope, journal, "REJECTED", "abgelehnt mit Begruendung",
                "Betreiber", recorded_at="2026-11-27T15:00:00+00:00",
            )
            with self.assertRaises(cr.ReviewBlockedError):
                cr.record_review(
                    envelope, journal, "TRIAGED", "nachziehen", "Betreiber",
                    recorded_at="2026-11-27T15:01:00+00:00",
                )

    def test_deferred_resumes_and_accepted_can_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            envelope = _envelope()
            cr.record_review(
                envelope, journal, "DEFERRED", "zuruegestellt", "Betreiber",
                recorded_at="2026-11-27T15:00:00+00:00",
            )
            cr.record_review(
                envelope, journal, "TESTING", "wieder im Test", "Betreiber",
                recorded_at="2026-11-27T15:01:00+00:00",
            )
            cr.record_review(
                envelope, journal, "ACCEPTED", "angenommen", "Betreiber",
                recorded_at="2026-11-27T15:02:00+00:00",
            )
            cr.record_review(
                envelope, journal, "REJECTED", "doch abgelehnt", "Betreiber",
                recorded_at="2026-11-27T15:03:00+00:00",
            )

    def test_self_approval_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            with self.assertRaises(cr.ReviewBlockedError) as ctx:
                cr.record_review(
                    _envelope(), journal, "TRIAGED", "eigenes OK",
                    "fremdes modell a",  # Gross/Kleinschreibung egal
                    recorded_at="2026-11-27T15:00:00+00:00",
                )
            self.assertIn("self-approval", str(ctx.exception))
            self.assertFalse(journal.exists())

    def test_empty_reason_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            with self.assertRaises(cr.ReviewBlockedError):
                cr.record_review(
                    _envelope(), journal, "TRIAGED", "   ", "Betreiber",
                    recorded_at="2026-11-27T15:00:00+00:00",
                )

    def test_invalid_envelope_blocked_by_reused_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            envelope = _envelope()
            del envelope["goal"]  # Pflichtfeld weg
            with self.assertRaises(cr.ReviewBlockedError) as ctx:
                cr.record_review(
                    envelope, journal, "TRIAGED", "x", "Betreiber",
                    recorded_at="2026-11-27T15:00:00+00:00",
                )
            self.assertIn("envelope rejected", str(ctx.exception))
            self.assertFalse(journal.exists())

    def test_naive_timestamp_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            with self.assertRaises(cr.ReviewBlockedError):
                cr.record_review(
                    _envelope(), journal, "TRIAGED", "x", "Betreiber",
                    recorded_at="2026-11-27T15:00:00",  # ohne Zeitzone
                )

    def test_recorded_at_kept_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            entry = cr.record_review(
                _envelope(), journal, "TRIAGED", "x", "Betreiber",
                recorded_at="2026-11-27T16:00:00+01:00",
            )
            self.assertEqual(entry["recorded_at"], "2026-11-27T16:00:00+01:00")

    def test_envelope_digest_binds_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            first = cr.record_review(
                _envelope(), journal, "TRIAGED", "x", "Betreiber",
                recorded_at="2026-11-27T15:00:00+00:00",
            )
            changed = _envelope()
            changed["goal"] = changed["goal"] + " (zweiter Stand)"
            second = cr.record_review(
                changed, journal, "TESTING", "y", "Betreiber",
                recorded_at="2026-11-27T15:01:00+00:00",
            )
            self.assertNotEqual(
                first["envelope_digest"], second["envelope_digest"]
            )
            self.assertEqual(len(first["envelope_digest"]), 64)

    def test_entry_grants_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = cr.record_review(
                _envelope(), Path(tmp) / "review.jsonl", "TRIAGED",
                "x", "Betreiber", recorded_at="2026-11-27T15:00:00+00:00",
            )
            self.assertEqual(entry["rights"], "NOT_GRANTED")
            self.assertEqual(entry["execution"], "NOT_PERFORMED")
            self.assertEqual(entry["protocol"], cr.JOURNAL_PROTOCOL)

    def test_append_preserves_existing_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            envelope = _envelope()
            cr.record_review(
                envelope, journal, "TRIAGED", "x", "Betreiber",
                recorded_at="2026-11-27T15:00:00+00:00",
            )
            before = journal.read_text(encoding="utf-8")
            cr.record_review(
                envelope, journal, "TESTING", "y", "Betreiber",
                recorded_at="2026-11-27T15:01:00+00:00",
            )
            after = journal.read_text(encoding="utf-8")
            self.assertTrue(after.startswith(before))  # append-only
            self.assertEqual(len(after.strip().splitlines()), 2)

    def test_two_contributions_keep_independent_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            first = _envelope()
            second = _envelope()
            second["contribution_id"] = "contrib-2026-11-27-002"
            cr.record_review(
                first, journal, "TRIAGED", "x", "Betreiber",
                recorded_at="2026-11-27T15:00:00+00:00",
            )
            cr.record_review(
                second, journal, "REJECTED", "y", "Betreiber",
                recorded_at="2026-11-27T15:01:00+00:00",
            )
            chains = cr.load_journal(journal)
            self.assertEqual(len(chains), 2)
            self.assertEqual(
                chains["contrib-2026-11-27-001"][0]["from_status"], "RECEIVED"
            )
            self.assertEqual(
                chains["contrib-2026-11-27-002"][0]["from_status"], "RECEIVED"
            )


class JournalIntegrityTest(unittest.TestCase):
    def test_corrupt_line_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            journal.write_text("not json\n", encoding="utf-8")
            with self.assertRaises(cr.JournalIntegrityError):
                cr.record_review(
                    _envelope(), journal, "TRIAGED", "x", "Betreiber",
                    recorded_at="2026-11-27T15:00:00+00:00",
                )
            self.assertEqual(
                journal.read_text(encoding="utf-8"), "not json\n"
            )  # unveraendert

    def test_chain_break_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "review.jsonl"
            entry = {
                "protocol": cr.JOURNAL_PROTOCOL,
                "contribution_id": "contrib-2026-11-27-001",
                "from_status": "RECEIVED",
                "to_status": "TESTING",  # Regelversto: RECEIVED->TESTING
                "reviewer": "Jemand",
                "reason": "alter Wildwuchs",
                "recorded_at": "2026-11-26T00:00:00+00:00",
                "envelope_digest": "0" * 64,
                "rights": "NOT_GRANTED",
                "execution": "NOT_PERFORMED",
            }
            journal.write_text(
                json.dumps(entry) + "\n", encoding="utf-8"
            )
            with self.assertRaises(cr.JournalIntegrityError):
                cr.load_journal(journal)

    def test_transitions_match_single_source_scale(self):
        self.assertEqual(
            set(cr.TRANSITIONS), set(contribution_intake.CONTRIBUTION_STATUSES)
        )
        for from_status, targets in cr.TRANSITIONS.items():
            self.assertTrue(targets <= contribution_intake.CONTRIBUTION_STATUSES)


class CliTest(unittest.TestCase):
    def _write_envelope(self, tmp: str) -> Path:
        path = Path(tmp) / "envelope.json"
        path.write_text(
            json.dumps(_envelope(), ensure_ascii=False), encoding="utf-8"
        )
        return path

    def test_cli_records_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = self._write_envelope(tmp)
            journal = Path(tmp) / "review.jsonl"
            code = cr.main([
                "--envelope", str(envelope), "--journal", str(journal),
                "--to", "TRIAGED", "--reason", "per CLI erfasst",
                "--reviewer", "Betreiber", "--at", "2026-11-27T15:00:00+00:00",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(len(journal.read_text(encoding="utf-8").strip().splitlines()), 1)

    def test_cli_blocked_transition_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = self._write_envelope(tmp)
            journal = Path(tmp) / "review.jsonl"
            code = cr.main([
                "--envelope", str(envelope), "--journal", str(journal),
                "--to", "ACCEPTED", "--reason", "Sprung",
                "--reviewer", "Betreiber", "--at", "2026-11-27T15:00:00+00:00",
            ])
            self.assertEqual(code, 1)
            self.assertFalse(journal.exists())

    def test_cli_unreadable_envelope_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            code = cr.main([
                "--envelope", str(bad), "--journal", str(Path(tmp) / "r.jsonl"),
                "--to", "TRIAGED", "--reason", "x",
                "--reviewer", "Betreiber", "--at", "2026-11-27T15:00:00+00:00",
            ])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

"""
Tests fuer controller/quorum_decision: Auswertung dauerhafter, vom
QuorumLedger verifizierter Ed25519-Abstimmungsbelege zu einer
quorum-basierten Entscheidung. Ordnungsunabhaengig, fail-closed,
ENTSCHEIDUNG != AUSFUEHRUNG.

Lokal ohne installiertes cryptography-Paket laufen alle reinen
Auswertungs-Tests mit einem Protokoll-Dummy (nur records(), wie vom
Modul dokumentiert). Der echte Ledger-Integrationstest laeuft in der CI,
wo cryptography vorhanden ist (SCRIPTED != INSTALLED).
"""
import tempfile
import unittest
from pathlib import Path

try:
    from controller.crypto_receipts import generate_signing_keypair
    from controller.quorum_ledger import QuorumLedger, build_signed_vote
    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - lokale Sandbox ohne cryptography
    _HAS_CRYPTO = False

from controller.agent_consensus import Decision
from controller.quorum_decision import (
    QuorumDecisionError,
    RecordedDecision,
    evaluate_recorded_votes,
)

DIGEST = "a" * 64


def record(agent, sequence, approve=True, digest=DIGEST, epoch=1,
           policy="v1"):
    return {
        "record_type": "quorum_vote",
        "signature_algorithm": "ED25519",
        "agent_id": agent,
        "proposal_digest": digest,
        "epoch": epoch,
        "sequence": sequence,
        "approve": approve,
        "issued_at": 1000,
        "policy_version": policy,
        "receipt_signature": "00" * 64,
    }


class FakeLedger:
    """Minimaler Protokoll-Dummy: nur records(), keine Krypto."""

    def __init__(self, records):
        self._records = list(records)

    def records(self):
        return tuple(self._records)


class ValidationTests(unittest.TestCase):

    def test_rejects_ledger_without_records(self):
        with self.assertRaises(QuorumDecisionError):
            evaluate_recorded_votes(object(), proposal_digest=DIGEST,
                                    epoch=1, policy_version="v1",
                                    member_ids=("a", "b", "c"))

    def test_rejects_bad_digest(self):
        with self.assertRaises(QuorumDecisionError):
            evaluate_recorded_votes(FakeLedger([]), proposal_digest="nothex",
                                    epoch=1, policy_version="v1",
                                    member_ids=("a", "b", "c"))

    def test_rejects_bad_epoch_and_policy(self):
        for epoch in (-1, "1", 1.0):
            with self.assertRaises(QuorumDecisionError):
                evaluate_recorded_votes(FakeLedger([]), proposal_digest=DIGEST,
                                        epoch=epoch, policy_version="v1",
                                        member_ids=("a", "b", "c"))
        with self.assertRaises(QuorumDecisionError):
            evaluate_recorded_votes(FakeLedger([]), proposal_digest=DIGEST,
                                    epoch=1, policy_version="  ",
                                    member_ids=("a", "b", "c"))

    def test_rejects_empty_or_malformed_members(self):
        for members in ((), [], ("a", "a"), ("a", "", "c"), "abc"):
            with self.assertRaises(QuorumDecisionError):
                evaluate_recorded_votes(FakeLedger([]), proposal_digest=DIGEST,
                                        epoch=1, policy_version="v1",
                                        member_ids=members)

    def test_rejects_out_of_range_quorum(self):
        with self.assertRaises(QuorumDecisionError):
            evaluate_recorded_votes(FakeLedger([]), proposal_digest=DIGEST,
                                    epoch=1, policy_version="v1",
                                    member_ids=("a", "b", "c"), quorum=4)
        with self.assertRaises(QuorumDecisionError):
            evaluate_recorded_votes(FakeLedger([]), proposal_digest=DIGEST,
                                    epoch=1, policy_version="v1",
                                    member_ids=("a", "b", "c"), quorum=0)


class EvaluationTests(unittest.TestCase):
    MEMBERS = ("agent-a", "agent-b", "agent-c")

    def evaluate(self, records, **kwargs):
        options = dict(proposal_digest=DIGEST, epoch=1, policy_version="v1",
                       member_ids=self.MEMBERS)
        options.update(kwargs)
        return evaluate_recorded_votes(FakeLedger(records), **options)

    def test_two_approvals_accept(self):
        result = self.evaluate([record("agent-a", 1, True),
                                record("agent-b", 2, True)])
        self.assertEqual(Decision.ACCEPT, result.decision)
        self.assertEqual(2, result.quorum_required)
        self.assertEqual(("agent-a", "agent-b"), result.yes)
        self.assertEqual((), result.no)
        self.assertEqual(2, result.matched_records)

    def test_one_yes_one_no_is_no_quorum(self):
        result = self.evaluate([record("agent-a", 1, True),
                                record("agent-b", 2, False)])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertEqual(("agent-a",), result.yes)
        self.assertEqual(("agent-b",), result.no)

    def test_two_rejections_reject(self):
        result = self.evaluate([record("agent-a", 1, False),
                                record("agent-b", 2, False)])
        self.assertEqual(Decision.REJECT, result.decision)
        self.assertEqual(("agent-a", "agent-b"), result.no)

    def test_missing_vote_is_neither_yes_nor_no(self):
        result = self.evaluate([record("agent-a", 1, True)])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertEqual(1, len(result.yes))
        self.assertEqual(0, len(result.no))

    def test_conflicting_votes_void_agent_contribution(self):
        result = self.evaluate([record("agent-a", 1, True),
                                record("agent-a", 2, True),
                                record("agent-b", 3, True)])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertEqual(("agent-b",), result.yes)
        self.assertIn("agent-a: conflicting recorded votes", result.excluded)

    def test_conflict_detection_is_order_independent(self):
        first = self.evaluate([record("agent-a", 2, True),
                              record("agent-a", 1, False),
                              record("agent-b", 3, True)])
        second = self.evaluate([record("agent-a", 1, False),
                               record("agent-a", 2, True),
                               record("agent-b", 3, True)])
        self.assertEqual(first, second)
        self.assertEqual(Decision.NO_QUORUM, first.decision)

    def test_other_ballot_records_ignored(self):
        result = self.evaluate([
            record("agent-a", 1, True),
            record("agent-b", 2, True, digest="b" * 64),
            record("agent-b", 3, True, epoch=2),
            record("agent-c", 4, True, policy="v2"),
        ])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertEqual(1, result.matched_records)
        self.assertEqual(("agent-a",), result.yes)

    def test_unconfigured_member_excluded(self):
        result = self.evaluate([record("agent-a", 1, True),
                                record("stranger", 2, True)])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertIn("stranger: not a configured member", result.excluded)
        self.assertEqual(2, result.matched_records)

    def test_malformed_record_envelope_excluded_not_crashing(self):
        result = self.evaluate(["not-a-dict", record("agent-a", 1, True)])
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        self.assertIn("malformed record envelope", result.excluded)

    def test_explicit_quorum_three_requires_three(self):
        records = [record("agent-a", 1, True), record("agent-b", 2, True)]
        result = self.evaluate(records, quorum=3)
        self.assertEqual(Decision.NO_QUORUM, result.decision)
        records.append(record("agent-c", 3, True))
        result = self.evaluate(records, quorum=3)
        self.assertEqual(Decision.ACCEPT, result.decision)

    def test_result_type_is_frozen_dataclass(self):
        result = self.evaluate([])
        self.assertIsInstance(result, RecordedDecision)
        with self.assertRaises(Exception):
            result.decision = Decision.ACCEPT


@unittest.skipUnless(_HAS_CRYPTO, "cryptography nicht installiert (CI lifted)")
class RealLedgerIntegrationTests(unittest.TestCase):
    """Echte End-zu-End-Kette: signieren -> anhaengen -> neuladen -> auswerten."""

    def test_persistent_two_of_three_accept(self):
        agents = ("agent-a", "agent-b", "agent-c")
        keys = {a: generate_signing_keypair() for a in agents}
        public = {a: pub for a, (_, pub) in keys.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum.jsonl"
            ledger = QuorumLedger(path, public)
            for agent, approve in (("agent-a", True), ("agent-b", True)):
                ledger.append_vote(build_signed_vote(
                    agent_id=agent, proposal_digest=DIGEST, epoch=1,
                    sequence=1, approve=approve, issued_at=1000,
                    policy_version="v1", private_key=keys[agent][0]))
            reloaded = QuorumLedger(path, public)  # Persistenzbeweis
            result = evaluate_recorded_votes(
                reloaded, proposal_digest=DIGEST, epoch=1,
                policy_version="v1", member_ids=agents)
            self.assertEqual(Decision.ACCEPT, result.decision)
            self.assertEqual(("agent-a", "agent-b"), result.yes)
            self.assertEqual(2, reloaded.entry_count())

    def test_real_ledger_rejects_forged_sequence(self):
        agents = ("agent-a", "agent-b", "agent-c")
        keys = {a: generate_signing_keypair() for a in agents}
        public = {a: pub for a, (_, pub) in keys.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum.jsonl"
            ledger = QuorumLedger(path, public)
            ledger.append_vote(build_signed_vote(
                agent_id="agent-a", proposal_digest=DIGEST, epoch=1,
                sequence=2, approve=True, issued_at=1000,
                policy_version="v1", private_key=keys["agent-a"][0]))
            with self.assertRaises(Exception):
                ledger.append_vote(build_signed_vote(
                    agent_id="agent-a", proposal_digest=DIGEST, epoch=1,
                    sequence=1, approve=False, issued_at=1000,
                    policy_version="v1", private_key=keys["agent-a"][0]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

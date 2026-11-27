"""Tests: V91 Issue #492 Stufe-1 Text-Abgleich (controller/comms_text_abgleich).

Alle Pruefungen laufen gegen die realen Repository-Dokumente; keine
Netzwerkzugriffe, keine Schreibvorgaenge. TEXTABGLEICH != INHALTSPRUEFUNG.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from controller import comms_text_abgleich as cta
from controller import contribution_intake as ci

REPO_ROOT = Path(__file__).resolve().parent.parent

COMMS_TEXT = (REPO_ROOT / cta.COMMS_DOC_PATH).read_text(encoding="utf-8")
CONTRIBUTION_TEXT = (REPO_ROOT / cta.CONTRIBUTION_DOC_PATH).read_text(
    encoding="utf-8"
)
SCHEMA_TEXT = (REPO_ROOT / cta.SCHEMA_PATH).read_text(encoding="utf-8")

REPORT = cta.compare_texts(
    COMMS_TEXT, CONTRIBUTION_TEXT, SCHEMA_TEXT,
    {"evidence": tuple(ci.EVIDENCE_STATUSES),
     "workflow": tuple(ci.CONTRIBUTION_STATUSES)},
)


class TestChainExtraction(unittest.TestCase):
    def test_evidence_chain_comms_matches_reference(self):
        self.assertEqual(tuple(REPORT["evidence_chain_comms"]), cta.EVIDENCE_CHAIN)

    def test_evidence_chain_contribution_matches_reference(self):
        self.assertEqual(
            tuple(REPORT["evidence_chain_contribution"]), cta.EVIDENCE_CHAIN
        )

    def test_evidence_chain_identical_between_documents(self):
        self.assertTrue(REPORT["evidence_chain_identical"])

    def test_workflow_chain_in_comms_absent(self):
        # Dokumentierter Befund: COMMS-1 kennt KEINE Beitrags-Workflow-Kette.
        self.assertIsNone(REPORT["workflow_chain_in_comms"])

    def test_workflow_chain_in_contribution_matches_reference(self):
        self.assertTrue(REPORT["workflow_chain_matches_reference"])
        self.assertEqual(
            tuple(REPORT["workflow_chain_in_contribution"]), cta.WORKFLOW_CHAIN
        )

    def test_schema_enums_match_chains(self):
        self.assertTrue(REPORT["schema_evidence_enum_matches"])
        self.assertTrue(REPORT["schema_workflow_enum_matches"])

    def test_code_chains_match_reference(self):
        self.assertTrue(REPORT["code_evidence_chain_matches"])
        self.assertTrue(REPORT["code_workflow_chain_matches"])


class TestFieldComparison(unittest.TestCase):
    def test_comms_task_fields_extracted(self):
        self.assertEqual(
            REPORT["comms_task_fields"],
            ["task_id", "goal", "scope", "constraints", "authorization",
             "environment", "input_refs", "expected_evidence", "status",
             "result", "artifacts", "next_action"],
        )

    def test_contribution_fields_extracted(self):
        self.assertEqual(
            REPORT["contribution_fields"],
            ["protocol", "contribution_id", "origin", "goal", "scope",
             "inputs_and_provenance", "proposed_change", "interfaces",
             "tests_and_evidence", "known_limits", "security_privacy_notes",
             "status", "next_action", "license"],
        )

    def test_field_overlap(self):
        self.assertEqual(REPORT["field_overlap"], ["goal", "next_action", "scope", "status"])

    def test_semantic_divergence_status_field_is_documented(self):
        # 'status' ist in COMMS-1 ein Evidenzstatus, in CONTRIBUTION-1 ein
        # uebermittelter Workflow-Anspruch: Ueberlappung != Bedeutungsgleich.
        self.assertIn("status", REPORT["field_overlap"])


class TestRuleCounterparts(unittest.TestCase):
    def test_all_rule_counterparts_found(self):
        self.assertTrue(REPORT["all_rule_counterparts_found"])

    def test_rule_counterpart_keys_stable(self):
        self.assertEqual(
            sorted(REPORT["rule_counterpart_findings"]),
            sorted([
                "claim_is_not_evidence",
                "no_secrets_in_public_channels",
                "untrusted_external_content",
                "no_authorization_granted",
                "isolation_before_integration",
                "offline_usable",
            ]),
        )


class TestPurityAndStability(unittest.TestCase):
    def test_inputs_unmodified(self):
        self.assertEqual(
            (REPO_ROOT / cta.COMMS_DOC_PATH).read_text(encoding="utf-8"),
            COMMS_TEXT,
        )
        self.assertEqual(
            (REPO_ROOT / cta.CONTRIBUTION_DOC_PATH).read_text(encoding="utf-8"),
            CONTRIBUTION_TEXT,
        )

    def test_report_deterministic(self):
        again = cta.compare_texts(
            COMMS_TEXT, CONTRIBUTION_TEXT, SCHEMA_TEXT,
            {"evidence": tuple(ci.EVIDENCE_STATUSES),
             "workflow": tuple(ci.CONTRIBUTION_STATUSES)},
        )
        self.assertEqual(json.dumps(REPORT, sort_keys=True),
                         json.dumps(again, sort_keys=True))

    def test_negative_probe_rejects_altered_chain(self):
        broken = CONTRIBUTION_TEXT.replace("VERIFIED", "VERIFIZIERT", 1)
        report = cta.compare_texts(COMMS_TEXT, broken, SCHEMA_TEXT, None)
        self.assertFalse(report["evidence_chain_identical"])

    def test_compare_repo_files_path_is_absolute_safe(self):
        report = cta.compare_repo_files(str(REPO_ROOT))
        self.assertTrue(report["evidence_chain_identical"])


if __name__ == "__main__":
    unittest.main()

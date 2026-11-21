#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests fuer controller/quorum_status_report.py (Issue #167 Punkt 10,
VIBE-XXXIII). Alle Tests deterministisch, kein Netz, keine echten
Provider, keine Credentials (UNIT_TESTED != API_INTEGRATION_VERIFIED).
"""
from __future__ import annotations

import unittest

from controller.quorum_status_report import (
    Evidence,
    QuorumStatusReportError,
    QuorumStatusRegistry,
    VERIFICATION_STAGES,
    parse_evidence,
)


def _evidence(kind: str, detail: str) -> Evidence:
    return Evidence(kind, detail)


def _full_chain(registry: QuorumStatusRegistry, component: str) -> None:
    kinds = ["DESIGN_DOC", "MODULE_PATH", "UNIT_RUN", "PROVIDER_CONFIG",
             "QUORUM_DECISION", "EXECUTION_RECEIPT"]
    for stage, kind in zip(VERIFICATION_STAGES, kinds):
        registry.register(component, stage, _evidence(kind, "ref:%s:%s" % (component, stage)))


class EvidenceTests(unittest.TestCase):

    def test_rejects_non_string_fields(self):
        with self.assertRaises(QuorumStatusReportError):
            Evidence(1, "x")  # type: ignore[arg-type]
        with self.assertRaises(QuorumStatusReportError):
            Evidence("DESIGN_DOC", 2)  # type: ignore[arg-type]

    def test_rejects_empty_and_whitespace_detail(self):
        with self.assertRaises(QuorumStatusReportError):
            Evidence("DESIGN_DOC", "")
        with self.assertRaises(QuorumStatusReportError):
            Evidence("DESIGN_DOC", "   ")

    def test_rejects_empty_kind(self):
        with self.assertRaises(QuorumStatusReportError):
            Evidence("", "doc")

    def test_rejects_oversized_detail(self):
        with self.assertRaises(QuorumStatusReportError):
            Evidence("DESIGN_DOC", "x" * 201)


class RegistryStageFlowTests(unittest.TestCase):

    def setUp(self):
        self.registry = QuorumStatusRegistry()

    def test_first_registration_must_be_designed(self):
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("quorum_evaluator", "UNIT_TESTED",
                                    _evidence("UNIT_RUN", "t"))

    def test_one_step_advance_is_recorded(self):
        self.registry.register("agent_quorum", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("agent_quorum", "IMPLEMENTED", _evidence("MODULE_PATH", "controller/agent_quorum.py"))
        self.assertEqual(self.registry.stage_of("agent_quorum"), "IMPLEMENTED")

    def test_stage_jump_refused(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "UNIT_TESTED", _evidence("UNIT_RUN", "t"))

    def test_regression_refused_without_reset(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("c", "IMPLEMENTED", _evidence("MODULE_PATH", "p"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d again"))

    def test_same_stage_refused(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d2"))

    def test_full_chain_reaches_execution_verified(self):
        _full_chain(self.registry, "chain")
        self.assertEqual(self.registry.stage_of("chain"), "EXECUTION_VERIFIED")

    def test_reset_requires_reason_and_removes_component(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.reset_component("c", "")
        self.registry.reset_component("c", "design withdrawn")
        with self.assertRaises(QuorumStatusReportError):
            self.registry.stage_of("c")

    def test_reset_unknown_component_refused(self):
        with self.assertRaises(QuorumStatusReportError):
            self.registry.reset_component("ghost", "reason")

    def test_after_reset_fresh_start_at_designed(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.reset_component("c", "withdrawn")
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d2"))
        self.assertEqual(self.registry.stage_of("c"), "DESIGNED")


class EvidenceKindGateTests(unittest.TestCase):

    def setUp(self):
        self.registry = QuorumStatusRegistry()
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("c", "IMPLEMENTED", _evidence("MODULE_PATH", "p"))

    def test_unit_tested_requires_unit_run_evidence(self):
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "UNIT_TESTED", _evidence("DESIGN_DOC", "wrong kind"))
        self.registry.register("c", "UNIT_TESTED", _evidence("UNIT_RUN", "20/20 local"))
        self.assertEqual(self.registry.stage_of("c"), "UNIT_TESTED")

    def test_self_promotion_to_api_integration_refused_with_unit_run(self):
        self.registry.register("c", "UNIT_TESTED", _evidence("UNIT_RUN", "20/20 local"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "API_INTEGRATION_VERIFIED",
                                   _evidence("UNIT_RUN", "still only unit"))
        self.assertEqual(self.registry.stage_of("c"), "UNIT_TESTED")

    def test_api_integration_needs_provider_config(self):
        self.registry.register("c", "UNIT_TESTED", _evidence("UNIT_RUN", "20/20 local"))
        self.registry.register("c", "API_INTEGRATION_VERIFIED",
                               _evidence("PROVIDER_CONFIG", "approved-store://provider-a"))
        self.assertEqual(self.registry.stage_of("c"), "API_INTEGRATION_VERIFIED")

    def test_quorum_verified_needs_quorum_decision(self):
        _full_chain(self.registry, "q")
        self.assertEqual(self.registry.stage_of("q"), "EXECUTION_VERIFIED")

    def test_execution_verified_needs_execution_receipt(self):
        self.registry.register("c", "UNIT_TESTED", _evidence("UNIT_RUN", "t"))
        self.registry.register("c", "API_INTEGRATION_VERIFIED",
                               _evidence("PROVIDER_CONFIG", "cfg"))
        self.registry.register("c", "QUORUM_VERIFIED", _evidence("QUORUM_DECISION", "ledger:42"))
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c", "EXECUTION_VERIFIED", _evidence("QUORUM_DECISION", "no"))
        self.registry.register("c", "EXECUTION_VERIFIED",
                               _evidence("EXECUTION_RECEIPT", "receipt:abc"))
        self.assertEqual(self.registry.stage_of("c"), "EXECUTION_VERIFIED")

    def test_unknown_stage_refused(self):
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c2", "MIRACLE_VERIFIED", _evidence("DESIGN_DOC", "d"))

    def test_none_stage_refused_not_guessed(self):
        with self.assertRaises(QuorumStatusReportError):
            self.registry.register("c2", None, _evidence("DESIGN_DOC", "d"))


class ComponentNameTests(unittest.TestCase):

    def test_rejects_empty_and_oversized_names(self):
        registry = QuorumStatusRegistry()
        with self.assertRaises(QuorumStatusReportError):
            registry.register("", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        with self.assertRaises(QuorumStatusReportError):
            registry.register("x" * 65, "DESIGNED", _evidence("DESIGN_DOC", "d"))

    def test_evidence_instance_required(self):
        registry = QuorumStatusRegistry()
        with self.assertRaises(QuorumStatusReportError):
            registry.register("c", "DESIGNED", "DESIGN_DOC raw string")


class ReportTests(unittest.TestCase):

    def setUp(self):
        self.registry = QuorumStatusRegistry()

    def test_report_sorted_and_copied(self):
        _full_chain(self.registry, "b_component")
        self.registry.register("a_component", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        report = self.registry.report()
        self.assertEqual([r["component"] for r in report],
                         ["a_component", "b_component"])
        report[0]["stage"] = "TAMPERED"
        self.assertEqual(self.registry.stage_of("a_component"), "DESIGNED")

    def test_report_contains_evidence_copy(self):
        self.registry.register("c", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        entry = self.registry.report()[0]
        self.assertEqual(entry["evidence"], {"kind": "DESIGN_DOC", "detail": "d"})
        entry["evidence"]["kind"] = "TAMPERED"
        self.assertEqual(self.registry.report()[0]["evidence"]["kind"], "DESIGN_DOC")

    def test_summary_counts_stages(self):
        self.registry.register("a", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("b", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("d", "DESIGNED", _evidence("DESIGN_DOC", "d"))
        self.registry.register("d", "IMPLEMENTED", _evidence("MODULE_PATH", "p"))
        self.registry.register("d", "UNIT_TESTED", _evidence("UNIT_RUN", "t"))
        summary = self.registry.summary()
        self.assertEqual(summary["DESIGNED"], 2)
        self.assertEqual(summary["UNIT_TESTED"], 1)
        self.assertEqual(summary["EXECUTION_VERIFIED"], 0)


class ParseEvidenceTests(unittest.TestCase):

    def test_parse_exact_fields_ok(self):
        ev = parse_evidence({"kind": "DESIGN_DOC", "detail": "docs/x.md"})
        self.assertEqual(ev.kind, "DESIGN_DOC")
        self.assertEqual(ev.detail, "docs/x.md")

    def test_parse_rejects_extra_and_missing_fields(self):
        with self.assertRaises(QuorumStatusReportError):
            parse_evidence({"kind": "DESIGN_DOC"})
        with self.assertRaises(QuorumStatusReportError):
            parse_evidence({"kind": "K", "detail": "d", "extra": 1})
        with self.assertRaises(QuorumStatusReportError):
            parse_evidence("not-a-mapping")


if __name__ == "__main__":
    unittest.main()

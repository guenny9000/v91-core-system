"""Documentation contract tests for the V91 Erkenntnis- und Revisionsprotokoll."""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "V91-ERKENNTNIS-UND-REVISIONSPROTOKOLL.md"


class ErkenntnisRevisionProtokollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.flat = re.sub(r"\s+", " ", cls.text)

    def test_document_exists_and_is_bounded(self):
        self.assertTrue(DOC.is_file())
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_ascii_encoding_contract(self):
        self.assertTrue(all(ord(ch) < 128 for ch in self.text))

    def test_truth_is_not_granted_by_a_status_marker(self):
        self.assertIn("Wahrheit bezeichnet die Wirklichkeit", self.flat)
        self.assertIn("kann Wahrheit nicht per", self.flat)

    def test_display_glyphs_have_stable_codepoint_mapping(self):
        for codepoint in ("U+003F", "U+25C9", "U+223F", "U+2713",
                          "U+2197", "U+27F3", "U+25C7", "U+0021",
                          "U+2727"):
            self.assertIn(codepoint, self.text)

    def test_all_status_markers_are_defined(self):
        for marker in ("CLAIM", "OBS", "MEAS", "VER", "IMP", "REMEAS",
                       "UNK", "DISPUTED", "REV"):
            self.assertIn(marker, self.text)

    def test_unknown_and_disputed_are_not_success(self):
        self.assertIn("UNKNOWN != PASS", self.text)
        self.assertIn("DISPUTED", self.text)
        self.assertIn("NICHT_GEPRUEFT", self.text)

    def test_measurement_provenance_fields_are_required(self):
        for field in ("Quelle", "Zeitpunkt", "Methode", "Unsicherheitsangabe",
                      "Verantwortliche", "Wiederholbarkeit"):
            self.assertIn(field, self.text)

    def test_verification_scope_is_bounded(self):
        for rule in ("Test bestanden != System sicher oder produktiv",
                     "Hash stimmt != Inhalt wahr",
                     "CI gruen != Realbetrieb"):
            self.assertIn(rule, self.flat)

    def test_improvement_requires_baseline_and_remeasurement(self):
        self.assertIn("vor der Aenderung festgelegte Baseline", self.flat)
        self.assertIn("REMEAS benoetigt", self.flat)
        self.assertIn("NICHT NACHGEWIESEN", self.text)

    def test_revision_is_transversal_not_final_stage(self):
        self.assertIn("Revision ist kein letzter Schritt nach REMEAS", self.flat)
        self.assertIn("ICH KOENNTE MICH IRREN", self.text)

    def test_revision_preserves_provenance(self):
        self.assertIn("nicht still ueberschrieben", self.flat)
        self.assertIn("Provenienz bleibt sichtbar", self.flat)

    def test_cultural_sources_are_not_relabelled(self):
        for rule in ("keine V91-Bedeutung", "MYTHOS != SPEZIFIKATION",
                     "ANALOGIE != BEWEIS", "ERZAEHLUNG != VERTRAG"):
            self.assertIn(rule, self.text)

    def test_no_automatic_authority_or_runtime_claim(self):
        for rule in ("keine automatische Steuerung",
                     "keine Berechtigung",
                     "Dokumentiert != implementiert"):
            self.assertIn(rule, self.text)

    def test_existing_governance_is_referenced_not_duplicated(self):
        self.assertIn("docs/V91-AUDIT-KERN.md", self.text)
        self.assertIn("MAX-BEST-GELUEBNIS/PROTOCOL", self.text)
        self.assertIn("docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md", self.text)

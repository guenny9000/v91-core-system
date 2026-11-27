"""V91-Sonden fuer die #492-Bestandsaufnahme (26.11.2026).

Diese Tests verriegeln die Verdikte der Bestandsaufnahme
docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md und die STALE-Korrektur
in docs/V91-KERN-BRIDGE-INTAKE.md gegen ihre eigenen festen
Aussagen (Doku-Pinning, gleiche Methode wie test_v91_repo_audit_review.py).
BELEGT != GELOEST: kein Verdikt dieser Datei behauptet einen Fix;
die Stufe-4-Luecke bleibt ausdruecklich offen und markiert.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "V91-492-BESTANDSAUFNAHME-2026-11-26.md"
INTAKE = ROOT / "docs" / "V91-KERN-BRIDGE-INTAKE.md"

MAX_DOC_BYTES = 8192
MESSTAND = "dc887e4368d1b8b9b92c7cf21e1c478ba8253fb4"

# == dem echten Code am Messstand entnommene Konstanten (Live-Verifikation
# gegen controller/contribution_intake.py und schemas/contribution.schema.json;
# Verdikte beruhen auf dieser Messung, die Tests pinnen die Strings).
WORKFLOW_STATUSES = ("RECEIVED", "TRIAGED", "TESTING", "ACCEPTED",
                     "INTEGRATED", "REJECTED", "DEFERRED")
EVIDENCE_STATUSES = ("UNKNOWN", "DOCUMENTED", "IMPLEMENTED", "TESTED",
                     "VERIFIED", "AUDITED", "PRODUCTION")

VERDICTS = {
    1: "TEILWEISE",
    2: "BELEGT",
    3: "BELEGT",
    4: "LUECKE",
    5: "BELEGT",
    6: "TEILWEISE",
    7: "TEILWEISE",
    8: "BEWUSST_GESPERRT",
}


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _stage_line(text: str, stage: int) -> str:
    pattern = r"^## Stufe " + str(stage) + r":.*Verdikt: (\w+)$"
    match = re.search(pattern, text, re.MULTILINE)
    assert match is not None, "Stufe %d fehlt" % stage
    return match.group(1)


class BestandsaufnahmeStrukturTest(unittest.TestCase):
    def test_doc_exists_under_8kib(self):
        self.assertTrue(DOC.exists())
        self.assertLess(DOC.stat().st_size, MAX_DOC_BYTES)

    def test_doc_is_ascii(self):
        raw = DOC.read_bytes()
        self.assertTrue(all(b < 128 for b in raw))

    def test_messstand_sha_pinned(self):
        self.assertIn(MESSTAND, _doc_text())

    def test_all_eight_stages_present_with_verdicts(self):
        text = _doc_text()
        for stage, verdict in VERDICTS.items():
            self.assertEqual(_stage_line(text, stage), verdict,
                             "Stufe %d muss %s sein" % (stage, verdict))

    def test_only_four_verdict_words_used(self):
        text = _doc_text()
        used = set(re.findall(r"Verdikt: (\w+)", text))
        self.assertEqual(used, {"BELEGT", "TEILWEISE", "LUECKE",
                                "BEWUSST_GESPERRT"})

    def test_honesty_banner_present(self):
        text = _doc_text()
        self.assertIn("BESTANDSAUFNAHME != FIX", text)
        self.assertIn("BELEGT != GELOEST", text)
        self.assertIn("CLAIM != EVIDENCE", text)


class Stufe4LueckeEhrlichTest(unittest.TestCase):
    """Die gefundene Luecke darf nicht still behoben oder verharmlost werden."""

    def test_stage4_is_luecke_and_not_solved(self):
        self.assertEqual(VERDICTS[4], "LUECKE")
        text = _doc_text()
        self.assertIn("NICHT_GELOEST_BEKANNT", text)

    def test_no_solved_claim_for_open_stages(self):
        text = _doc_text()
        for stage in (1, 4, 6, 7):
            line = _stage_line(text, stage)
            self.assertNotIn("GELOEST", line)
            self.assertNotIn("BEHOBEN", line)

    def test_stage4_names_both_paths(self):
        text = _doc_text()
        self.assertIn("security_privacy_notes", text)
        self.assertIn("secret_scan", text)


class CodeKettenGepinntTest(unittest.TestCase):
    """Die im Doc zitierten Statusketten muessen exakt den Live-Konstanten
    entsprechen (Nachmessung 26.11. am main dc887e43)."""

    def test_workflow_status_chain_complete_in_doc(self):
        text = _doc_text()
        for status in WORKFLOW_STATUSES:
            self.assertIn(status, text)

    def test_evidence_status_chain_complete_in_doc(self):
        text = _doc_text()
        for status in EVIDENCE_STATUSES:
            self.assertIn(status, text)


class IntakeDocNachmessungTest(unittest.TestCase):
    """Die STALE-Korrektur im Intake-Standard muss Zahlen + Stand nennen."""

    def setUp(self):
        self.text = INTAKE.read_text(encoding="utf-8")

    def test_nachmessung_section_present(self):
        self.assertIn("## 5. Nachmessung 26.11.2026", self.text)

    def test_fresh_numbers_pinned(self):
        self.assertIn("11749 B", self.text)
        self.assertIn("22 Tests", self.text)
        self.assertIn("8 Verkettungs-Sonden", self.text)
        self.assertIn("8831 B", self.text)  # Screening-Baustein nach Telefon-+Adress-Erweiterung 27.11.
        self.assertIn("30 Screening-Tests", self.text)

    def test_messstand_and_stale_note_pinned(self):
        self.assertIn("dc887e4368d1b8b9b92c7cf21e1c478ba8253fb4", self.text)
        self.assertIn("Stufe 4", self.text)
        self.assertIn("V91-492-BESTANDSAUFNAHME-2026-11-26.md", self.text)

    def test_nachfuehrungsregel_pinned(self):
        self.assertIn("ZAHL == STAND != VERTRAG", self.text)


if __name__ == "__main__":
    unittest.main()

"""Tests: docs/V91-LERNBLOCK-MODELL-BRIDGE.md (Modell-Bridge, connector-freie KIs).

Doku-pinnende Tests: Der Lernblock darf keine Schnittstellen beschreiben,
die nicht existieren (NACHWEIS_VOR_SCHNITTSTELLE), und muss alle
referenzierten Pfade real existieren (ein referenzierter Pfad ist ein
Existenzversprechen gegenueber dem Betreiber; LERNBLOCK != IMPLEMENTATION).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "V91-LERNBLOCK-MODELL-BRIDGE.md"


class ModellBridgeLernblockTests(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC.is_file())

    def test_honest_header_and_status_rules(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("LERNBLOCK != IMPLEMENTATION", raw)
        self.assertIn("BRIDGE != VERBINDUNG", raw)
        self.assertIn("CLAIM != EVIDENCE", raw)
        self.assertIn("SCRIPTED != INSTALLED", raw)

    def test_no_phantom_api_claims(self):
        raw = DOC.read_text(encoding="utf-8")
        # Tako-API darf nur als NICHT BELEGT / nicht existent vorkommen
        self.assertIn("KEINE_TAKO_API", raw)
        for forbidden in (
            "Tako-API-Key",
            "Tako API-Key",
            "API-Schluessel von TikTok besorgen",
            "Hintergrundverbindung aktiv",
        ):
            self.assertNotIn(forbidden, raw)

    def test_referenced_paths_exist(self):
        raw = DOC.read_text(encoding="utf-8")
        for rel in [
            "docs/V91-ARCHITEKTUR-INDEX.md",
            "docs/V91_LEARNING_BLOCK_COMMUNICATION_PROTOCOL.md",
        ]:
            self.assertIn(rel, raw, f"doc must reference {rel}")
            self.assertTrue((REPO_ROOT / rel).is_file(),
                            f"referenced file missing: {rel}")

    def test_diagrams_and_code_present(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertEqual(raw.count("```mermaid"), 2, "zwei Ablaufdiagramme gepinnt")
        self.assertIn("```python", raw)
        self.assertIn("```text", raw)
        self.assertIn("flowchart TD", raw)

    def test_example_is_read_only(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("read-only", raw)
        self.assertIn("KEIN Schreibzugriff", raw)
        self.assertIn("https://api.github.com/repos/guenny9000/v91-core-system", raw)
        code = raw.split("```python", 1)[1].split("```", 1)[0]
        for forbidden in ["requests.post", "patch", "delete", "urlopen(req, data="]:
            self.assertNotIn(forbidden, code)

    def test_ascii_pure_no_tabs_no_umlaute(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertNotIn("\t", raw)
        for ch in raw:
            self.assertLess(ord(ch), 128,
                            f"non-ascii char {ch!r} in Lernblock")


if __name__ == "__main__":
    unittest.main()

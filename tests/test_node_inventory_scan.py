#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests fuer controller.node_inventory_scan (#276 Faehigkeit 1, Mess-Scanner).

Pinnen: reine Lesemessung, ehrliches UNKNOWN, keine erfundenen Owner oder
EOL-Urteile, fail-closed Auditor-Integration, keine Aktionen.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from controller import node_inventory  # noqa: E402
from controller import node_inventory_scan as nis  # noqa: E402


def make_node(tmp):
    root = os.path.join(tmp, "node")
    os.makedirs(os.path.join(root, "pkg"), exist_ok=True)
    with open(os.path.join(root, "pkg", "app.py"), "w", encoding="utf-8") as h:
        h.write("import os\nfrom pkg import util\n")
    with open(os.path.join(root, "pkg", "util.py"), "w", encoding="utf-8") as h:
        h.write("import json\n")
    with open(os.path.join(root, "pkg", "test_util.py"), "w", encoding="utf-8") as h:
        h.write("import unittest\nfrom pkg import util\n")
    with open(os.path.join(root, "ledger.jsonl"), "w", encoding="utf-8") as h:
        h.write('{"a": 1}\n')
    return root


class TestScanner(unittest.TestCase):
    def test_nur_gemesste_kinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            kinds = {c["kind"] for c in inv["components"]}
            self.assertEqual(kinds, {"software", "storage"})
            names = {c["name"] for c in inv["components"]}
            self.assertIn("app.py", names)
            self.assertIn("ledger.jsonl", names)

    def test_importbeziehungen_gemessen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            by_id = {c["component_id"]: c for c in inv["components"]}
            util_id = "node:pkg/util.py"
            self.assertIn("pkg/app.py", by_id[util_id]["measured"]["imported_by"])
            self.assertIn("pkg/test_util.py", by_id[util_id]["measured"]["imported_by"])
            self.assertTrue(by_id[util_id]["in_active_use"])

    def test_eol_bleibt_unknown_owner_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            for c in inv["components"]:
                self.assertEqual(c["eol_status"], "unknown")
                self.assertEqual(c["owner"], "unassigned-pending-review")
                self.assertTrue(c["evidence"]["source"])
                self.assertTrue(c["evidence"]["checked_on"])

    def test_keine_dienste_identitaeten_energie_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            for c in inv["components"]:
                self.assertNotIn(c["kind"], ("exposed_service", "identity", "key"))

    def test_scan_veraendert_nichts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            before = sorted(
                (os.path.relpath(os.path.join(dp, f), root), os.path.getsize(os.path.join(dp, f)))
                for dp, dn, fn in os.walk(root) for f in fn
            )
            nis.build_scanned_inventory("n1", root)
            after = sorted(
                (os.path.relpath(os.path.join(dp, f), root), os.path.getsize(os.path.join(dp, f)))
                for dp, dn, fn in os.walk(root) for f in fn
            )
            self.assertEqual(before, after)

    def test_fail_closed_fehlendes_root(self):
        with self.assertRaises(NotADirectoryError):
            nis.build_scanned_inventory("n1", "/nicht/da/xyz")


class TestAuditorIntegration(unittest.TestCase):
    def test_verdict_strukturell_complete_grenzen_dokumentiert(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            verdict = nis.audit_scanned(inv)
            # Auditor akzeptiert die gemessenen Records strukturell.
            self.assertEqual(verdict["decision"], "INVENTORY_COMPLETE")
            self.assertEqual(verdict["components_incomplete"], 0)
            self.assertEqual(verdict["components_unknown_eol"], len(inv["components"]))
            self.assertIn("COMPLETE != BETRIEFFUND", verdict["scan_limits"])

    def test_jede_komponente_durch_auditor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            inv = nis.build_scanned_inventory("n1", root)
            for comp in inv["components"]:
                res = node_inventory.validate_component(comp)
                self.assertEqual(res["result"], "OK", res["violations"])

    def test_kein_retire_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            open(os.path.join(root, "pkg", "leer.py"), "w").close()
            inv = nis.build_scanned_inventory("n1", root)
            for c in inv["components"]:
                self.assertNotIn(c["eol_status"], ("retire", "isolate", "replace"))


class TestCli(unittest.TestCase):
    def test_scan_cli_exit_und_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_node(tmp)
            out = os.path.join(tmp, "inv.json")
            r = subprocess.run(
                [sys.executable, nis.__file__, root, "--node-id", "n1", "--json-out", out],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            verdict = json.loads(r.stdout)
            self.assertEqual(verdict["decision"], "INVENTORY_COMPLETE")
            with open(out, "r", encoding="utf-8") as h:
                blob = json.load(h)
            self.assertEqual(blob["verdict"]["node_id"], "n1")
            self.assertGreater(len(blob["inventory"]["components"]), 0)


if __name__ == "__main__":
    unittest.main()

"""Tests fuer controller.bridge_screening und die kern_bridge-Verkabelung
(Stufe-4-Screening: Secrets/PII werden VOR der Ledger-Ablage redigiert).

Token-Literale werden aus FRAGMENTEN konstruiert, damit der CI-Schritt
controller/secret_scan.py keine vollstaendige hochsignalige Form in
DIESE Datei liest (REDAKTIONS-TEST != SECRET-AUSGABE). KEIN Netz, KEIN
echtes Geheimnis, KEIN echter GitHub-Kontakt.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import bridge_screening as bs
from controller import kern_bridge as kb
from controller import secret_scan as sc


def _ghp_token() -> str:
    return "gh" + "p_" + "A" * 36

def _akia_token() -> str:
    return "AK" + "IA" + "1" * 16

def _xox_token() -> str:
    return "xo" + "xb-" + "C" * 12

def _aiza_token() -> str:
    return "AI" + "za" + "D" * 35

def _glpat_token() -> str:
    return "gl" + "pat-" + "E" * 20

def _sk_token() -> str:
    return "s" + "k-" + "F" * 24

def _pat_token() -> str:
    return "github_" + "pat_" + "G" * 30

def _privkey_block() -> str:
    begin = "-----BEGIN " + "RSA " + "PRIVATE KEY-----"
    end = "-----END " + "RSA " + "PRIVATE KEY-----"
    body = "\n".join("H" * 64 for _ in range(3))
    return begin + "\n" + body + "\n" + end

def _iban() -> str:
    return "DE" + "9" * 20

def _wrapped(text: str) -> str:
    return (kb.HANDOVER_MARKER + "\n" + text + "\n" + kb.HANDOVER_END_MARKER)


class ScreenTextUnitTest(unittest.TestCase):
    def test_clean_text_unchanged(self):
        body = "Kernidee: schlichter Zaehler, keine Vertraulichkeit.\nZeile zwei."
        result = bs.screen_text(body)
        self.assertEqual(result["status"], bs.SCREENING_STATUS_CLEAN)
        self.assertEqual(result["redacted_text"], body)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["redaction_count"], 0)

    def test_github_classic_token_redacted(self):
        token = _ghp_token()
        result = bs.screen_text(_wrapped("token im text: " + token))
        self.assertEqual(result["status"], bs.SCREENING_STATUS_REDACTED)
        self.assertNotIn(token, result["redacted_text"])
        self.assertIn(bs.REDACTION_MARKER, result["redacted_text"])

    def test_aws_access_key_redacted(self):
        token = _akia_token()
        result = bs.screen_text("key wie " + token + " hier")
        self.assertNotIn(token, result["redacted_text"])
        self.assertIn("aws_access_key_id",
                      {f["kind"] for f in result["findings"]})

    def test_slack_and_google_and_gitlab_and_sk_redacted(self):
        for kind, token in (
            ("slack_token", _xox_token()),
            ("google_api_key", _aiza_token()),
            ("gitlab_token", _glpat_token()),
            ("sk_prefixed_key", _sk_token()),
        ):
            result = bs.screen_text("probe " + token + " probe")
            self.assertNotIn(token, result["redacted_text"], kind)
            self.assertIn(kind, {f["kind"] for f in result["findings"]}, kind)

    def test_fine_grained_token_redacted(self):
        token = _pat_token()
        result = bs.screen_text("neuer Stil " + token)
        self.assertNotIn(token, result["redacted_text"])
        self.assertIn("github_fine_grained_token",
                      {f["kind"] for f in result["findings"]})

    def test_private_key_block_multi_line_redacted(self):
        block = _privkey_block()
        result = bs.screen_text(_wrapped(block) + "\nnachspann")
        redacted = result["redacted_text"]
        self.assertNotIn("H" * 64, redacted)  # Koerperzeilen weg
        self.assertNotIn("RSA ", redacted.split("\n")[0] or "x")
        self.assertIn("nachspann", redacted)  # Text danach bleibt
        self.assertIn(("private_key_block", 2),
                      {(f["kind"], f["line_no"]) for f in result["findings"]})

    def test_email_redacted(self):
        result = bs.screen_text("mail an max@muster-domain.example senden")
        self.assertNotIn("max@muster-domain.example", result["redacted_text"])
        self.assertIn("email", {f["kind"] for f in result["findings"]})

    def test_iban_redacted_spaced_and_plain(self):
        for form in (_iban(), "DE99 " + "1234 5678 9012 3456 78"):
            result = bs.screen_text("konto " + form + " danke")
            self.assertNotIn(form.replace(" ", ""), result["redacted_text"].replace(" ", ""))
            self.assertIn("iban_de", {f["kind"] for f in result["findings"]})

    def test_quoted_assignment_value_redacted_keyword_kept(self):
        secret_value = "Zimme" + "rLinchen88"
        line = 'subscribe: password = "' + secret_value + '"'
        result = bs.screen_text(line)
        self.assertNotIn(secret_value, result["redacted_text"])
        self.assertIn("password", result["redacted_text"])
        self.assertIn("keyword_assignment",
                      {f["kind"] for f in result["findings"]})

    def test_placeholder_assignment_not_redacted(self):
        line = 'password = "beispiel-test-1234"'
        result = bs.screen_text(line)
        self.assertEqual(result["status"], bs.SCREENING_STATUS_CLEAN)
        self.assertIn("beispiel-test-1234", result["redacted_text"])

    def test_variable_reference_and_path_not_redacted(self):
        for line in ('token = "$GITHUB_TOKEN"', "api_key = '/run/secrets/key'"):
            result = bs.screen_text(line)
            self.assertEqual(result["status"], bs.SCREENING_STATUS_CLEAN, line)

    def test_multiple_findings_line_numbers_sorted(self):
        body = ("zeile eins ok\n"
                "token " + _ghp_token() + "\n"
                "mail max@muster-domain.example\n")
        result = bs.screen_text(body)
        pairs = [(f["line_no"], f["kind"]) for f in result["findings"]]
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual([p[0] for p in pairs], [2, 3])

    def test_findings_carry_no_secret_material(self):
        token = _ghp_token()
        result = bs.screen_text("x " + token + " y max@muster-domain.example z")
        dump = json.dumps(result["findings"])
        self.assertNotIn(token, dump)
        self.assertNotIn("muster-domain", dump)
        for finding in result["findings"]:
            self.assertEqual(sorted(finding), ["kind", "line_no"])

    def test_overlapping_matches_merge_to_single_marker(self):
        token = _ghp_token()
        line = 'token = "' + token + '"'
        result = bs.screen_text(line)
        self.assertEqual(result["redacted_text"].count(bs.REDACTION_MARKER), 1)
        self.assertNotIn(token, result["redacted_text"])

    def test_reuse_pin_same_pattern_objects_as_secret_scan(self):
        # NO_DUPLICATE: das Screening importiert die MUSTER, baut keine Kopie.
        self.assertIs(bs.HIGH_SIGNAL_PATTERNS, sc.HIGH_SIGNAL_PATTERNS)
        self.assertIs(bs.GENERIC_ASSIGNMENT_PATTERN, sc.GENERIC_ASSIGNMENT_PATTERN)
        self.assertIs(bs.ENV_ASSIGNMENT_PATTERN, sc.ENV_ASSIGNMENT_PATTERN)

    def test_pii_forms_are_documented_pair(self):
        self.assertEqual([kind for kind, _ in bs.PII_PATTERNS],
                         ["email", "iban_de",
                          "tel_international_de", "tel_national_de"])

    def test_telefon_international_geschrieben_redacted(self):
        for form in ("+49 30 12345678", "+4917612345678",
                     "+49/6621/123456"):
            result = bs.screen_text("ruf " + form + " an")
            self.assertNotIn(form, result["redacted_text"], form)
            self.assertIn("tel_international_de",
                          {f["kind"] for f in result["findings"]}, form)

    def test_telefon_national_geschrieben_redacted(self):
        for form in ("0176 1234 5678", "030-1234-567", "06621/12 34 56",
                     "0800 1234567"):
            result = bs.screen_text("ruf " + form + " an")
            self.assertNotIn(form, result["redacted_text"], form)
            self.assertIn("tel_national_de",
                          {f["kind"] for f in result["findings"]}, form)

    def test_telefon_kein_digitierter_nachbar(self):
        # Buchstaben unmittelbar vor/nach der Nummer duerfen NICHT
        # absorbiert werden; Ziffern-Zusatzgruppen (Durchwahl) werden
        # bewusst mitredigiert (dokumentiertes Over-Blocking).
        line = "id x0176 1234 5678y 34 Ende"
        result = bs.screen_text(line)
        self.assertNotIn("0176 1234 5678", result["redacted_text"])
        self.assertIn("y", result["redacted_text"])
        self.assertIn("34", result["redacted_text"])
        line2 = "ruf 0176 1234 5678 34 durchwahl"
        result2 = bs.screen_text(line2)
        self.assertNotIn("5678 34", result2["redacted_text"])  # absorbiert

    def test_keine_telefon_falschtreffer_alltag(self):
        for harmlos in ("Datum: 27.11.2026 im Bericht",
                        "PLZ 36041 Alsfeld",
                        "Uhrzeit 07:30 Uhr",
                        "kurz 0123 45 bleibt"):
            result = bs.screen_text(harmlos)
            self.assertEqual(result["status"], bs.SCREENING_STATUS_CLEAN, harmlos)
            self.assertNotIn("tel_", json.dumps(result["findings"]))

    def test_telefon_overblocking_isbn_dokumentiert(self):
        # Bekanntes, dokumentiertes Over-Blocking: ISBN mit fuehrender 0
        # wird mitredigiert (PII-SCHUTZ VOR BEQUEMLICHKEIT, reversibel).
        result = bs.screen_text("buch 0-306-40615-2 alt")
        self.assertIn("tel_national_de",
                      {f["kind"] for f in result["findings"]})

    def test_non_string_fails_closed(self):
        with self.assertRaises(TypeError):
            bs.screen_text(None)
        with self.assertRaises(TypeError):
            bs.screen_text(123)

    def test_honesty_limits_travel_with_result(self):
        result = bs.screen_text("ok")
        self.assertIn("MUSTER != GARANTIE", result["honesty_limits"])
        self.assertIn("GATE != SCREENING", result["honesty_limits"])


class BridgeIntakeScreeningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "v91_bridge_inbox.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _collect(self, issues):
        return kb.collect_kerns(
            self.ledger, fetch=lambda repo, label: list(issues))

    def test_secret_never_reaches_ledger_cleartext(self):
        token = _ghp_token()
        body = _wrapped("kern mit schlüssel " + token)
        report = self._collect([{"number": 1, "title": "k", "body": body}])
        raw = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn(token, raw)
        record = json.loads(raw.splitlines()[0])
        self.assertEqual(record["gate_status"], kb.GATE_ACCEPTED)
        self.assertEqual(record["screening_status"], bs.SCREENING_STATUS_REDACTED)
        self.assertIn("schlüssel", record["payload"])
        self.assertEqual(record["sha256"],
                         hashlib.sha256(body.encode("utf-8")).hexdigest())
        self.assertEqual(report["screening_counts"][bs.SCREENING_STATUS_REDACTED], 1)

    def test_blocked_pattern_and_secret_are_independent(self):
        token = _akia_token()
        body = _wrapped("code: rm -rf /tmp/x\nkey " + token)
        self._collect([{"number": 2, "title": "k", "body": body}])
        record = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["gate_status"], kb.GATE_BLOCKED)
        self.assertIn("rm -rf", record["payload"])  # ISOLATE_NOT_DESTROY bleibt
        self.assertNotIn(token, record["payload"])  # Redaktion bleibt

    def test_clean_body_stored_verbatim_with_clean_screening(self):
        body = kb.HANDOVER_MARKER + "\nKern alpha, harmlos\n" + kb.HANDOVER_END_MARKER
        report = self._collect([{"number": 3, "title": "k", "body": body}])
        record = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["payload"], body)
        self.assertEqual(record["screening_status"], bs.SCREENING_STATUS_CLEAN)
        self.assertEqual(record["screening_findings"], [])
        self.assertEqual(report["screening_counts"][bs.SCREENING_STATUS_CLEAN], 1)

    def test_dedup_uses_raw_hash_across_redaction(self):
        token = _ghp_token()
        body = _wrapped("dup " + token)
        self._collect([{"number": 4, "title": "k", "body": body}])
        second = self._collect([{"number": 4, "title": "k", "body": body}])
        self.assertEqual(second["records_new"], 0)
        self.assertEqual(second["records_known"], 1)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 1)

    def test_gate_states_unchanged_by_screening(self):
        self.assertEqual(kb.GATE_ACCEPTED, "ACCEPTED_ISOLATED")
        self.assertEqual(kb.GATE_BLOCKED, "BLOCKED_PATTERN")
        self.assertEqual(kb.GATE_MISSING_MARKER, "MISSING_HANDOVER_MARKER")
        self.assertNotIn("SCREENING", kb.GATE_ACCEPTED)


if __name__ == "__main__":
    unittest.main()

"""Tests: Audit-Ketten-Inspektor (controller/audit_chain_inspect).

Drei Faelle aus dem Betreiber-Entwurf (MISSING/VALID/CORRUPTED) plus
Verriegelung des Review-Fixes: der ERSTE Eintrag muss von GENESIS_HASH
ketten. Alle Ketten werden synthetisch erzeugt (KEINE echten Daten)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from controller.audit_chain_inspect import (
    GENESIS_HASH,
    _canonical_digest,
    inspect_audit_chain,
)


def _make_entry(status: str, previous_digest: str) -> dict:
    body = {
        "timestamp_utc": "2026-11-27T18:00:00+00:00",
        "subject_id": "SOLAR-DESKTOP-01",
        "status": status,
        "previous_digest_sha256": previous_digest,
    }
    body["digest_sha256"] = _canonical_digest(body)
    return body


def _write_chain(tmp: Path, name: str, entries: list) -> Path:
    chain = tmp / name
    chain.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
        encoding="utf-8",
    )
    return chain


class TestBetreiberFaelle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v91_audit_chain_"))

    def test_missing_chain(self):
        summary = inspect_audit_chain(self.tmp / "does_not_exist.jsonl")
        self.assertEqual(summary.status, "MISSING_CHAIN")
        self.assertEqual(summary.total_records, 0)
        self.assertEqual(summary.status_counts, {})
        self.assertIn("CHAIN_FILE_MISSING", summary.errors)
        self.assertEqual(len(summary.digest_sha256), 64)

    def test_valid_chain(self):
        first = _make_entry("VERIFIED_BENEFIT", GENESIS_HASH)
        second = _make_entry("UNVERIFIED_PENDING_LOCAL_EVIDENCE", first["digest_sha256"])
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [first, second])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "VALID_CHAIN")
        self.assertEqual(summary.total_records, 2)
        self.assertEqual(summary.status_counts, {
            "UNVERIFIED_PENDING_LOCAL_EVIDENCE": 1,
            "VERIFIED_BENEFIT": 1,
        })
        self.assertEqual(summary.errors, [])

    def test_corrupted_chain_on_hash_modification(self):
        first = _make_entry("VERIFIED_BENEFIT", GENESIS_HASH)
        second = _make_entry("VERIFIED_BENEFIT", first["digest_sha256"])
        tampered_first = dict(first, digest_sha256="0" * 64)
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [tampered_first, second])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "CORRUPTED_CHAIN")
        self.assertEqual(summary.total_records, 2)
        self.assertIn("line_1:DIGEST_MISMATCH", summary.errors)
        self.assertIn("line_2:PREV_DIGEST_MISMATCH", summary.errors)


class TestReviewFixGenesisRegel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v91_audit_chain_"))

    def test_erster_eintrag_ohne_genesis_prev_wird_erroet(self):
        # Original-Luecke: Zeile 1 mit beliebigem Vorgaenger-Digest ging
        # durch; nach dem Review-FIX schlaegt sie an.
        first = _make_entry("VERIFIED_BENEFIT", "f" * 64)
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [first])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "CORRUPTED_CHAIN")
        self.assertIn("line_1:PREV_DIGEST_MISMATCH", summary.errors)

    def test_erster_eintrag_mit_genesis_prev_valid(self):
        first = _make_entry("VERIFIED_BENEFIT", GENESIS_HASH)
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [first])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "VALID_CHAIN")


class TestRandfaelle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v91_audit_chain_"))

    def test_leere_datei_valid_mit_null_records(self):
        chain = self.tmp / "audit_chain.jsonl"
        chain.write_text("", encoding="utf-8")
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "VALID_CHAIN")
        self.assertEqual(summary.total_records, 0)
        self.assertEqual(summary.status_counts, {})

    def test_leerzeilen_und_kein_dict_und_kaputte_zeile(self):
        first = _make_entry("PENDING", GENESIS_HASH)
        chain = self.tmp / "audit_chain.jsonl"
        chain.write_text(
            "\n" + json.dumps(first) + "\n"
            + json.dumps([1, 2, 3]) + "\n"
            + "{not json\n",
            encoding="utf-8",
        )
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "CORRUPTED_CHAIN")
        self.assertEqual(summary.total_records, 3)
        self.assertIn("line_3:ENTRY_NOT_DICT", summary.errors)
        self.assertTrue(any(e.startswith("line_4:JSON_DECODE_ERROR") for e in summary.errors))
        self.assertEqual(summary.status_counts, {"PENDING": 1})

    def test_status_fehlt_zaehlt_als_unknown(self):
        body = {"timestamp_utc": "2026-11-27T18:00:00+00:00",
                "previous_digest_sha256": GENESIS_HASH}
        body["digest_sha256"] = _canonical_digest(body)
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [body])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status_counts, {"UNKNOWN": 1})
        self.assertEqual(summary.status, "VALID_CHAIN")

    def test_zwei_eintraege_nach_tamper_noch_nachvollziehbar(self):
        first = _make_entry("A", GENESIS_HASH)
        second = _make_entry("B", first["digest_sha256"])
        tampered = dict(second, status="B_TAMPERED")  # Inhalt geaendert,
        # digest behauptet unverstaendig weiter -> DIGEST_MISMATCH
        chain = _write_chain(self.tmp, "audit_chain.jsonl", [first, tampered])
        summary = inspect_audit_chain(chain)
        self.assertEqual(summary.status, "CORRUPTED_CHAIN")
        self.assertIn("line_2:DIGEST_MISMATCH", summary.errors)


if __name__ == "__main__":
    unittest.main()

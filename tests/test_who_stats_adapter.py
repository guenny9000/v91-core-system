"""Tests fuer den WHO-Stats-Adapter (CLAIM != EVIDENCE, UNKNOWN != PASS).

ALLES ohne Netz (injizierter Stub-Fetcher); der reale urlopen-Pfad
wird bewusst NICHT getestet (SCRIPTED != RUNNING, Tests != Betrieb).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "controller"))

from controller import who_stats_adapter as who
from controller.ledger import HashChainLedger, verify_chain
from controller import measurement_ingest
from controller import iea_stats_adapter as iea


def stub_fetch_mit_key(url, api_key):
    assert "api_key" not in url  # Schluessel gehoert in den Header
    return json.dumps({"values": {"lebenserwartung_jahre": 78.9,
                                  "as_of": "2026-01-01T00:00:00Z"}})


def stub_fetch_offen(url):
    # offener Abruf: ohne Key-Argument
    return json.dumps({"values": {"impfquote_anteil": 0.93,
                                  "as_of": "2026-01-01T00:00:00Z"}})


class LedgerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = HashChainLedger(
            str(Path(self.tmp.name) / "who_ledger.jsonl"))

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        with open(self.ledger.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


class PollValid(LedgerBase):
    def setUp(self):
        super().setUp()
        import os
        os.environ["WHO_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "WHO_API_KEY", None)

    def test_valid_wert_wird_geprueft_und_gebucht(self):
        rec = who.poll_once(
            self.ledger, "lebenserwartung_jahre", "DEU",
            fetch=stub_fetch_mit_key,
            url_builder=lambda m, r: "https://api.example/%s/%s" % (m, r))
        self.assertEqual(rec["status"], "VALID")
        self.assertTrue(abs(rec["wert"] - 78.9) < 1e-12)
        self.assertEqual(rec["quelle_ts"], "2026-01-01T00:00:00Z")
        self.assertEqual(rec["quelle"], "who-stats")
        self.assertEqual(rec["sensor_id"], "who-stats:DEU")
        self.assertFalse(rec["abruf_ohne_key"])
        self.assertIn("CLAIM != EVIDENCE", rec["honesty_limits"])
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)

    def test_offener_abruf_ohne_key_mit_require_false(self):
        rec = who.poll_once(
            self.ledger, "impfquote_anteil", "DEU",
            api_key_env="WHO_KEY_GIBT_ES_NICHT", require_api_key=False,
            fetch=stub_fetch_offen,
            url_builder=lambda m, r: "https://api.example/%s" % m)
        self.assertEqual(rec["status"], "VALID")
        self.assertTrue(abs(rec["wert"] - 0.93) < 1e-12)
        self.assertTrue(rec["abruf_ohne_key"])

    def test_schluessel_nur_aus_env_nicht_in_url(self):
        import os
        os.environ["WHO_TEST_KEY"] = "k-123"
        self.addCleanup(os.environ.pop, "WHO_TEST_KEY", None)
        who.poll_once(self.ledger, "lebenserwartung_jahre", "DEU",
                      api_key_env="WHO_TEST_KEY",
                      fetch=stub_fetch_mit_key,
                      url_builder=lambda m, r: "https://api.example/")
        self.assertEqual(len(self.records()), 1)


class PollUnknown(LedgerBase):
    """Fehlende Werte werden EXPLIZIT als UNKNOWN gebucht, nie 0."""

    def _rec(self, **kw):
        import os
        os.environ["WHO_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "WHO_API_KEY", None)
        who.poll_once(self.ledger, kw.get("metric",
                                          "lebenserwartung_jahre"),
                      "DEU", **{k: v for k, v in kw.items()
                                if k != "metric"})
        return self.records()[-1]["payload"]

    def test_require_api_key_ohne_key_not_configured(self):
        rec = who.poll_once(
            self.ledger, "lebenserwartung_jahre", "DEU",
            api_key_env="WHO_KEY_GIBT_ES_NICHT", require_api_key=True,
            fetch=stub_fetch_mit_key,
            url_builder=lambda m, r: "u")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(rec["wert"])
        self.assertEqual(rec["fehler_status"], "NOT_CONFIGURED")
        self.assertIn("WHO_KEY_GIBT_ES_NICHT", rec["grund"])
        self.assertTrue(rec["abruf_ohne_key"])

    def test_fetch_oder_url_builder_fehlt_not_configured(self):
        rec = self._rec()
        self.assertEqual(rec["fehler_status"], "NOT_CONFIGURED")
        self.assertIsNone(rec["wert"])

    def test_wert_fehlt_in_quelle(self):
        rec = self._rec(
            fetch=lambda u, k: json.dumps({"values": {}}),
            url_builder=lambda m, r: "u")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(rec["wert"])

    def test_quarantaene_ausserhalb_wertebereich(self):
        rec = self._rec(
            fetch=lambda u, k: json.dumps(
                {"values": {"impfquote_anteil": 7.5}}),
            url_builder=lambda m, r: "u", metric="impfquote_anteil")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertEqual(rec["rohwert"], 7.5)
        self.assertEqual(rec["fehler_status"], "QUARANTINE")

    def test_netzfehler_explizit_nicht_crash(self):
        def boese(url, key):
            raise OSError("netz weg")
        rec = self._rec(fetch=boese, url_builder=lambda m, r: "u")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertEqual(rec["fehler_status"], "QUARANTINE")
        self.assertIn("abruf fehlgeschlagen", rec["grund"])

    def test_unbekannte_metrik_fail_closed(self):
        with self.assertRaises(ValueError):
            who.poll_once(self.ledger, "sonnenflecken_index", "DEU",
                          fetch=stub_fetch_mit_key,
                          url_builder=lambda m, r: "u")

    def test_kein_stiller_verwurf_jeder_fehlschlag_gebucht(self):
        who.poll_once(self.ledger, "lebenserwartung_jahre", "DEU",
                      api_key_env="NOPE_NOPE")
        who.poll_once(self.ledger, "lebenserwartung_jahre", "DEU",
                      api_key_env="NOPE_NOPE")
        who.poll_once(self.ledger, "impfquote_anteil", "DEU",
                      api_key_env="NOPE_NOPE")
        recs = [line["payload"] for line in self.records()]
        self.assertEqual(len(recs), 3)
        self.assertTrue(all(r["wert"] is None for r in recs))
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)


class AdapterRegeln(unittest.TestCase):
    def test_metric_specs_reuse_measurement_ingest(self):
        for name, spec in who.METRIC_SPECS.items():
            self.assertIsInstance(spec, measurement_ingest.SensorSpec)
        self.assertLess(
            who.METRIC_SPECS["lebenserwartung_jahre"].maximum, 121.0)
        self.assertLess(
            who.METRIC_SPECS["impfquote_anteil"].maximum, 1.1)
        self.assertLess(
            who.METRIC_SPECS["gesundheitsausgaben_bip_anteil"].maximum,
            1.1)

    def test_sensor_id_namensraum_getrennt_von_iea(self):
        self.assertNotEqual(who.SOURCE_ID, iea.SOURCE_ID)
        self.assertNotIn("who_stats_adapter", dir(iea))

    def test_honesty_limits_enthalten_kernregeln(self):
        self.assertIn("UNKNOWN != PASS", who.HONESTY_LIMITS)
        self.assertIn("KATALOG != SENSOR", who.HONESTY_LIMITS)
        self.assertIn("OFFENER_ABRUF", who.HONESTY_LIMITS)

    def test_parse_who_fail_closed(self):
        self.assertEqual(who.parse_who_payload("kein json"), {})
        self.assertEqual(who.parse_who_payload("[1,2,3]"), {})
        self.assertEqual(who.parse_who_payload('{"values": 5}'), {})
        self.assertEqual(who.parse_who_payload('{"values": {"x": 1}}'),
                         {"x": 1})


class PollBatch(LedgerBase):
    def setUp(self):
        super().setUp()
        import os
        os.environ["WHO_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "WHO_API_KEY", None)

    def test_batch_ein_record_je_metrik(self):
        def fetch(url, key):
            assert "k-test" not in url
            if "lebenserwartung" in url:
                return json.dumps(
                    {"values": {"lebenserwartung_jahre": 78.9}})
            return json.dumps(
                {"values": {"impfquote_anteil": 0.93}})
        recs = who.poll_batch(
            self.ledger, ["lebenserwartung_jahre", "impfquote_anteil"],
            "DEU", fetch=fetch,
            url_builder=lambda m, r: "https://api.example/" + m)
        self.assertEqual(len(recs), 2)
        self.assertEqual([r["status"] for r in recs],
                         ["VALID", "VALID"])
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)

    def test_batch_sequenz_reproduzierbar(self):
        seen = []
        def fetch(url, key):
            seen.append(url)
            return json.dumps({"values": {"lebenserwartung_jahre": 78.9}})
        who.poll_batch(self.ledger, ["lebenserwartung_jahre"], "DEU",
                       fetch=fetch,
                       url_builder=lambda m, r: "https://api.example/")
        self.assertTrue(all("k-test" not in u for u in seen))


if __name__ == "__main__":
    unittest.main()

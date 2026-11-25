"""Tests fuer den IEA-Stats-Adapter ( CLAIM != EVIDENCE, UNKNOWN != PASS).

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

from controller import iea_stats_adapter as iea
from controller.ledger import HashChainLedger, verify_chain
from controller import measurement_ingest


def stub_fetch_ok(url, api_key):
    assert "api_key" not in url  # Schluessel gehoert in den Header
    return json.dumps({"values": {"strommix_anteil": 0.34,
                                  "as_of": "2026-11-01T00:00:00Z"}})


class LedgerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = HashChainLedger(
            str(Path(self.tmp.name) / "iea_ledger.jsonl"))

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        with open(self.ledger.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


class PollValid(LedgerBase):
    def setUp(self):
        super().setUp()
        import os
        os.environ["IEA_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "IEA_API_KEY", None)

    def test_valid_wert_wird_geschaelt_und_gebuch(self):
        rec = iea.poll_once(
            self.ledger, "strommix_anteil", "DEU",
            fetch=stub_fetch_ok,
            url_builder=lambda m, r: "https://api.example/%s/%s" % (m, r))
        self.assertEqual(rec["status"], "VALID")
        self.assertTrue(abs(rec["wert"] - 0.34) < 1e-12)
        self.assertEqual(rec["quelle_ts"], "2026-11-01T00:00:00Z")
        self.assertIn("CLAIM != EVIDENCE", rec["honesty_limits"])
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)

    def test_schluessel_nur_aus_env_nicht_in_url(self):
        import os
        os.environ["IEA_TEST_KEY"] = "k-123"
        self.addCleanup(os.environ.pop, "IEA_TEST_KEY", None)
        iea.poll_once(self.ledger, "strommix_anteil", "DEU",
                      api_key_env="IEA_TEST_KEY", fetch=stub_fetch_ok,
                      url_builder=lambda m, r: "https://api.example/")
        self.assertEqual(len(self.records()), 1)


class PollUnknown(LedgerBase):
    """Fehlende Werte werden EXPLIZIT als UNKNOWN gebucht, nie 0."""

    def _rec(self, **kw):
        import os
        os.environ["IEA_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "IEA_API_KEY", None)
        iea.poll_once(self.ledger, kw.get("metric", "strommix_anteil"),
                      "DEU", **{k: v for k, v in kw.items()
                                if k != "metric"})
        return self.records()[-1]["payload"]

    def test_kein_api_key_not_configured(self):
        rec = iea.poll_once(self.ledger, "strommix_anteil", "DEU",
                           api_key_env="IEA_KEY_GIBT_ES_NICHT")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(rec["wert"])
        self.assertEqual(rec["fehler_status"], "NOT_CONFIGURED")
        self.assertIn("IEA_KEY_GIBT_ES_NICHT", rec["grund"])

    def test_wert_fehlt_in_quelle(self):
        rec = self._rec(
            fetch=lambda u, k: json.dumps({"values": {}}),
            url_builder=lambda m, r: "u")
        self.assertEqual(rec["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(rec["wert"])

    def test_quarantaene_ausserhalb_wertebereich(self):
        rec = self._rec(
            fetch=lambda u, k: json.dumps(
                {"values": {"strommix_anteil": 7.5}}),
            url_builder=lambda m, r: "u")
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
            iea.poll_once(self.ledger, "erdbeben_magnitude", "DEU",
                          fetch=stub_fetch_ok,
                          url_builder=lambda m, r: "u")

    def test_kein_stiller_verwurf_jede_nullzahl_gebucht(self):
        # drei schiefgegangene Abrufe -> DREI UNKNOWN-Records in Kette
        iea.poll_once(self.ledger, "strommix_anteil", "DEU",
                      api_key_env="NOPE_NOPE")
        iea.poll_once(self.ledger, "strommix_anteil", "DEU",
                      api_key_env="NOPE_NOPE")
        iea.poll_once(self.ledger, "co2_intensitaet", "DEU",
                      api_key_env="NOPE_NOPE")
        recs = [line["payload"] for line in self.records()]
        self.assertEqual(len(recs), 3)
        self.assertTrue(all(r["wert"] is None for r in recs))
        self.assertTrue(all(not (r["wert"] == 0) for r in recs))
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)


class AdapterRegeln(unittest.TestCase):
    def test_metric_specs_reuse_measurement_ingest(self):
        for name, spec in iea.METRIC_SPECS.items():
            self.assertIsInstance(spec, measurement_ingest.SensorSpec)
        self.assertIn("co2_intensitaet", iea.METRIC_SPECS)
        self.assertLess(iea.METRIC_SPECS["strommix_anteil"].maximum, 1.1)

    def test_fao_who_nicht_behauptet(self):
        """FAO/WHO-Adapter existieren auf main NICHT: der IEA-Adapter
        formuliert NUR das gemeinsame Protokoll, keine Existenz."""
        self.assertNotIn("fao_poll", dir(iea))
        self.assertNotIn("who_poll", dir(iea))
        self.assertIn("poll_once", iea.ADAPTER_PROTOCOL)
        self.assertIn("UNKNOWN != PASS", iea.HONESTY_LIMITS)

    def test_parse_iea_fail_closed(self):
        self.assertEqual(iea.parse_iea_payload("kein json"), {})
        self.assertEqual(iea.parse_iea_payload("[1,2,3]"), {})
        self.assertEqual(iea.parse_iea_payload('{"values": 5}'), {})


if __name__ == "__main__":
    unittest.main()


class CrossCheck(unittest.TestCase):
    """Cross-Check gegen Katalog-Evidenz: KONGRUENZ != VERIFIZIERT."""

    def test_kongruent(self):
        b = iea.cross_check(0.34, {"fao": 0.34, "who": 0.34})
        self.assertEqual(b["status"], iea.KATALOG_KONGRUENT)
        self.assertEqual(b["uebereinstimmung"], {"fao": 0.34, "who": 0.34})

    def test_divergent(self):
        b = iea.cross_check(0.34, {"fao": 0.34, "who": 0.90})
        self.assertEqual(b["status"], iea.KATALOG_DIVERGENT)
        self.assertEqual(b["abweichungen"], {"who": 0.90})

    def test_toleranz(self):
        b = iea.cross_check(0.34, {"fao": 0.341}, toleranz=0.01)
        self.assertEqual(b["status"], iea.KATALOG_KONGRUENT)
        with self.assertRaises(ValueError):
            iea.cross_check(0.34, {"fao": 0.34}, toleranz=-0.1)

    def test_keine_evidenz(self):
        self.assertEqual(iea.cross_check(0.34, {}).get("grund"),
                         "keine Evidenzquellen vorhanden")
        b = iea.cross_check(0.34, {"fao": None})
        self.assertEqual(b["status"], iea.NICHT_GEPRUEFT)

    def test_claim_fehlt(self):
        b = iea.cross_check(None, {"fao": 0.34})
        self.assertEqual(b["status"], iea.NICHT_GEPRUEFT)

    def test_bool_und_nan_evidenz_zaehlen_als_fehlend(self):
        b = iea.cross_check(0.34, {"a": True, "b": float("nan")})
        self.assertEqual(b["status"], iea.NICHT_GEPRUEFT)
        self.assertEqual(sorted(b["evidenz_fehlend"]), ["a", "b"])


class CrossCheckRecord(LedgerBase):
    """JEDE Cross-Check-Ebene erzeugt GENAU EINEN Ledger-Record."""

    def test_divergent_landet_als_unknown_mit_abweichungen(self):
        rec = iea.cross_check_record(
            self.ledger, "strommix_anteil", "DEU", 0.34,
            {"fao": 0.34, "who": 0.90})
        self.assertEqual(rec["status"], iea.NICHT_GEPRUEFT)
        self.assertEqual(rec["fehler_status"], iea.KATALOG_DIVERGENT)
        self.assertEqual(rec["abweichungen"], {"who": 0.90})
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)

    def test_kongruent_bleibt_claim_nicht_verifiziert(self):
        rec = iea.cross_check_record(
            self.ledger, "strommix_anteil", "DEU", 0.34, {"fao": 0.34})
        self.assertEqual(rec["status"], iea.KATALOG_KONGRUENT)
        self.assertIn("KONGRUENZ != VERIFIZIERT", rec["hinweis"])
        self.assertNotIn("VERIFIED", rec["status"])


class PollBatch(LedgerBase):
    def setUp(self):
        super().setUp()
        import os
        os.environ["IEA_API_KEY"] = "k-test"
        self.addCleanup(os.environ.pop, "IEA_API_KEY", None)

    def test_batch_ein_record_je_metrik(self):
        def fetch(url, key):
            assert "api_key" not in url  # Schluessel im Header, nie URL
            if "strommix" in url:
                return json.dumps({"values": {"strommix_anteil": 0.34}})
            return json.dumps({"values": {"co2_intensitaet": 420.0}})
        recs = iea.poll_batch(
            self.ledger, ["strommix_anteil", "co2_intensitaet"], "DEU",
            fetch=fetch,
            url_builder=lambda m, r: "https://api.example/" + m)
        self.assertEqual(len(recs), 2)
        self.assertEqual([r["status"] for r in recs],
                         ["VALID", "VALID"])
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(verify_chain(self.ledger.path)["chain_valid"],
                         True)

    def test_batch_sequenz_key_nie_in_url(self):
        gesehene = []
        def fetch(url, key):
            gesehene.append(url)
            return json.dumps({"values": {"strommix_anteil": 0.34}})
        iea.poll_batch(self.ledger, ["strommix_anteil"], "DEU",
                       fetch=fetch,
                       url_builder=lambda m, r: "https://api.example/")
        self.assertTrue(all("k-test" not in u for u in gesehene))

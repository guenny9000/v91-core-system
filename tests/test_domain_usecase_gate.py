import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / "controller")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from domain_usecase_gate import (  # noqa: E402
    DOMAINS,
    DomainUseCaseError,
    VERDICT_ERFUELLT,
    VERDICT_REVIEW,
    evaluate_domain_claim,
)


def _base_claim(domains, assessments):
    return {
        "claim_id": "claim-1",
        "claimant": "test-runner",
        "touched_domains": domains,
        "assessments": assessments,
    }


def test_all_domains_honest_unknown_ausgewiesen():
    claim = _base_claim(
        sorted(DOMAINS),
        {d: {"status": "UNKNOWN"} for d in DOMAINS},
    )
    result = evaluate_domain_claim(claim)
    assert result["verdict"] == VERDICT_ERFUELLT
    assert result["fehlende_ausweisung"] == []
    assert result["domains_belegt"] == 0
    assert result["domains_total"] == 6


def test_belegt_with_valid_evidence():
    claim = _base_claim(
        ["D1"],
        {
            "D1": {
                "status": "BELEGT",
                "evidence": "https://example.org/testprotokoll-d1",
                "source": "Testprotokoll Notfallkommunikation",
                "assessed_at": "2026-11-23T18:00:00+00:00",
            }
        },
    )
    result = evaluate_domain_claim(claim)
    assert result["verdict"] == VERDICT_ERFUELLT
    assert result["domains_belegt"] == 1
    assert result["ausweisungen"]["D1"]["belegt"] is True
    assert result["ausweisungen"]["D1"]["evidenz_referenzen"] == 1


def test_belegt_without_evidence_rejected():
    claim = _base_claim(
        ["D2"],
        {
            "D2": {
                "status": "BELEGT",
                "source": "Uebungsprotokoll",
                "assessed_at": "2026-11-23T18:00:00+00:00",
            }
        },
    )
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "CLAIM != EVIDENCE" in str(exc)
    else:
        raise AssertionError("BELEGT ohne Evidenz muss verweigert werden")


def test_belegt_with_bare_text_evidence_rejected():
    claim = _base_claim(
        ["D4"],
        {
            "D4": {
                "status": "BELEGT",
                "evidence": "steht im Bericht drin",
                "source": "Bericht",
                "assessed_at": "2026-11-23T18:00:00+00:00",
            }
        },
    )
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "EVIDENCE_SUPPLIED != EVIDENCE_VALID" in str(exc)
    else:
        raise AssertionError("nackter Text ist keine Evidenz-Referenz")


def test_belegt_with_naive_timestamp_rejected():
    claim = _base_claim(
        ["D3"],
        {
            "D3": {
                "status": "BELEGT",
                "evidence": "doi:10.0000/example",
                "source": "Migrationsanalyse",
                "assessed_at": "2026-11-23 18:00:00",
            }
        },
    )
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "zeitzonen-bewusst" in str(exc)
    else:
        raise AssertionError("naiver Zeitstempel muss verweigert werden")


def test_unknown_domain_rejected():
    claim = _base_claim(["D7"], {})
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "D7" in str(exc)
    else:
        raise AssertionError("unbekannte Domaenen-ID muss verweigert werden")


def test_empty_touched_domains_rejected():
    claim = _base_claim([], {})
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError:
        pass
    else:
        raise AssertionError("leere touched_domains muessen verweigert werden")


def test_duplicate_domain_rejected():
    claim = _base_claim(["D1", "D1"], {"D1": {"status": "UNKNOWN"}})
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "doppelt" in str(exc)
    else:
        raise AssertionError("doppelte Domaenen muessen verweigert werden")


def test_missing_assessment_yields_review_required():
    claim = _base_claim(["D1", "D2"], {"D1": {"status": "IN ARBEIT"}})
    result = evaluate_domain_claim(claim)
    assert result["verdict"] == VERDICT_REVIEW
    assert result["fehlende_ausweisung"] == ["D2"]


def test_invalid_status_rejected():
    claim = _base_claim(["D5"], {"D5": {"status": "FERTIG"}})
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "FERTIG" in str(exc)
    else:
        raise AssertionError("unbekannter Status muss verweigert werden")


def test_assessment_for_untouched_domain_rejected():
    claim = _base_claim(["D1"], {"D1": {"status": "UNKNOWN"}, "D6": {"status": "UNKNOWN"}})
    try:
        evaluate_domain_claim(claim)
    except DomainUseCaseError as exc:
        assert "D6" in str(exc)
    else:
        raise AssertionError("Ausweisung fuer unberuehrte Domaene muss verweigert werden")


def test_valid_evidence_with_honest_status_allowed():
    claim = _base_claim(
        ["D6"],
        {"D6": {"status": "VORSCHLAG", "evidence": "ledger::speicher-katalog-430"}},
    )
    result = evaluate_domain_claim(claim)
    assert result["verdict"] == VERDICT_ERFUELLT
    assert result["ausweisungen"]["D6"]["evidenz_referenzen"] == 1
    assert result["ausweisungen"]["D6"]["belegt"] is False


def test_cli_roundtrip_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(_base_claim(["D1"], {"D1": {"status": "NICHT GEPRUEFT"}})),
        encoding="utf-8",
    )
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(_base_claim(["D1", "D2"], {"D1": {"status": "UNKNOWN"}})), encoding="utf-8")
    module_path = ROOT / "controller" / "domain_usecase_gate.py"
    # Skript-Modus setzt sys.path[0] auf controller/ - v99 ist nur mit
    # explizitem PYTHONPATH (Repo-Wurzel) importierbar (echter CI-Befund).
    import os as _os
    env = dict(_os.environ)
    env["PYTHONPATH"] = str(ROOT) + (_os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    rc_good = subprocess.run(
        [sys.executable, str(module_path), "--claim-json", str(good)], cwd=str(ROOT), env=env
    ).returncode
    rc_missing = subprocess.run(
        [sys.executable, str(module_path), "--claim-json", str(missing)], cwd=str(ROOT), env=env
    ).returncode
    assert rc_good == 0
    assert rc_missing == 1

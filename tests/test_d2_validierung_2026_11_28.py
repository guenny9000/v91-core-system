"""D2-Validierung 2026-11-28: ONE-SHOT-Ergebnis verriegelt (ehrlich).

Macro-F1 0.8239 < 0.900 -> NICHT_BESTANDEN, FN=0 -> erfuellt.
KEIN_NACHFITTEN: Diese Tests pinnen das Ergebnis, damit keine spaetere
Runde es still 'verbessert'. VALIDIERUNG != GUETEORM.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATENBASIS = REPO_ROOT / "docs/cascade-history/v91-ci-suiten-2026-11-27-bis-28.jsonl"
DOKU = REPO_ROOT / "docs/V91-D2-VALIDIERUNG-2026-11-28.md"
AUSWERTER = REPO_ROOT / "controller/cascade_history_eval.py"


def _eval() -> dict:
    r = subprocess.run([sys.executable, str(AUSWERTER), str(DATENBASIS)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_datenbasis_wellformed_und_grenzen():
    zeilen = [json.loads(z) for z in DATENBASIS.read_text(encoding="utf-8").splitlines() if z.strip()]
    assert len(zeilen) == 44
    for z in zeilen:
        assert set(z) == {"branch", "head_sha", "suite_red", "suite_start_utc"}
        assert isinstance(z["suite_red"], bool)
    assert sum(1 for z in zeilen if z["suite_red"]) == 2
    erste = min(z["suite_start_utc"] for z in zeilen)
    assert erste >= "2026-11-27T15:48", "Stichtag der Vorregistrierung verletzt"


def test_ergebnis_nicht_bestanden_ehrlich():
    e = _eval()
    kaskade = e["detectors"]["detector_kaskade_prev_rot"]
    assert kaskade["confusion"] == {"tp": 1, "fp": 1, "fn": 0, "tn": 26}
    assert kaskade["macro_f1"] < 0.900, "Macro-F1-Kriterium war >= 0.900"
    assert round(kaskade["macro_f1"], 4) == 0.8239
    assert kaskade["confusion"]["fn"] == 0, "FN-Kriterium"
    assert e["follow_pairs"] == 28
    assert e["state"] == "EVALUATED"


def test_doku_pinnt_ergebnis_und_grenzen():
    text = DOKU.read_text(encoding="utf-8")
    for phrase in ("NICHT_BESTANDEN", "0.8239", "FN=0", "ONE-SHOT",
                   "KEIN_NACHFITTEN", "KEINE_SIGNIFIKANZ_BEI_KLEINEM_N",
                   "CLAIM != EVIDENCE"):
        assert phrase in text, phrase
    assert "BESTANDEN" in text and "NICHT BESTANDEN" in text

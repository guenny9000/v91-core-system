#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Betriebsprobe-Kit fuer das Forum-Claim-Ledger (Taskboard-Konvention
Phase 6, VIBE-XLVIII). Fuehrt EINEN selbstaendigen, vollstaendigen
Lebenszyklus in einem temporaeren Ledger aus und gibt einen
maschinenlesbaren PROBE-Report: jede Stufe ist PASS oder FAIL
(SKIP nur bei nachweislich fehlender Voraussetzung). Die Probe ist
die Vorbedingung fuer die Taskplaner-Frage (Ewigbetrieb-Doku #272):
PROBE ist ein technischer Betriebsnachweis-CANDIDATE am jeweiligen
Standort, KEIN Dauerbetriebsnachweis.

EXIT-CODES (deterministisch):
- 0 PROBE_PASSED (alle Stufen PASS)
- 1 Nutzungs-/Eingabefehler (ungueltige Argumente, Report nicht schreibbar)
- 2 REQUIREMENTS_MISSING (kein echtes Ed25519-Backend; STUB != ECHT,
  ein Stub-Beweis waere KEIN Beweis) oder PROBE_FAILED (eine Stufe FAIL)
- 3 I/O-Fehler

Ehrliche Grenzen (bewusst, nicht Luecken):
- STUB != ECHT: Ohne echtes cryptography-Backend verweigert die Probe
  komplett statt einen Schein-Nachweis zu erzeugen.
- PROBE != BETRIEB: Ein Durchlauf beweist, dass die Kette am Standort
  funktioniert, NICHT dass ein Taskplaner laeuft. KIT != INSTALLED.
- SIGNATURE != TRUTH, UNKNOWN != PASS: verifizierte Ereignisse
  beweisen Schluesselherrschaft, nicht die Wahrheit von Angaben.
- Die Probe erzeugt und vernichtet NUR ihre eigenen temporaeren
  Dateien; sie beruehrt KEINE echten Ledgers, KEINE echten Keys.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from io import StringIO
from unittest import mock

PROBE_NAME = "v91_betriebsprobe"
BASE_SHA = "a" * 40

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FAILED_OR_MISSING = 2
EXIT_IO = 3


def _has_real_ed25519() -> Optional[str]:
    """Prueft das ECHTE Backend: Import + Schluessel-Roundtrip.
    Rueckgabe None = echt, sonst ehrlicher Fehlertyp."""
    if importlib.util.find_spec("cryptography") is None:
        return "cryptography_module_missing"
    try:
        cr = importlib.import_module("controller.crypto_receipts")
        priv, pub = cr.generate_signing_keypair()
        probe_payload = {"record_type": "probe", "n": 1}
        signed = cr.sign_record(probe_payload, priv)
        probe_payload[cr.SIGNATURE_FIELD] = signed
        if not cr.verify_record_signature(probe_payload, pub):
            return "ed25519_roundtrip_failed"
        probe_payload["n"] = 2
        if cr.verify_record_signature(probe_payload, pub):
            return "ed25519_tamper_not_detected"
    except Exception as exc:  # pragma: no cover - unbekannte Backend-Fehler
        return "crypto_backend_error: " + type(exc).__name__
    return None


class ProbeStage:
    def __init__(self, name: str):
        self.name = name
        self.status = "FAIL"
        self.detail: Dict[str, Any] = {}

    def passed(self, detail: Optional[Dict[str, Any]] = None) -> "ProbeStage":
        self.status = "PASS"
        self.detail = detail or {}
        return self

    def failed(self, reason: str, detail: Optional[Dict[str, Any]] = None) -> "ProbeStage":
        self.status = "FAIL"
        self.detail = dict(detail or {})
        self.detail["reason"] = reason
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {"stage": self.name, "status": self.status, "detail": self.detail}


def _run_cli(argv: List[str]) -> Dict[str, Any]:
    """Fuehrt einen CLI-Runner in-process aus und faengt stdout und
    exit-code. Ausnahmen sind Nutzungsfehler (fail-closed, nie still)."""
    from scripts import v91_claim_cli
    from scripts import v91_watchdog

    module = v91_watchdog if argv[0] in ("scan", "expire") else v91_claim_cli
    buf = StringIO()
    with mock.patch("sys.stdout", buf):
        try:
            code = module.main([str(a) for a in argv])
        except SystemExit as exc:  # pragma: no cover
            code = int(exc.code or 0)
        except Exception as exc:
            return {"exit": 1, "error": type(exc).__name__ + ": " + str(exc), "payload": {}}
    out = buf.getvalue().strip()
    try:
        payload = json.loads(out) if out else {}
    except json.JSONDecodeError:
        payload = {"_raw": out[:200]}
    return {"exit": code, "payload": payload}


class Probe:
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.now = int(time.time())
        self.stages: List[ProbeStage] = []

    def _stage(self, name: str) -> ProbeStage:
        s = ProbeStage(name)
        self.stages.append(s)
        return s

    # -- Stufen ------------------------------------------------------

    def stage_keygen(self) -> None:
        from controller import crypto_receipts as cr

        worker_priv, worker_pub = cr.generate_signing_keypair()
        op_priv, op_pub = cr.generate_signing_keypair()
        probe_payload = {"record_type": "keyprobe", "who": "worker"}
        probe_payload[cr.SIGNATURE_FIELD] = cr.sign_record(probe_payload, worker_priv)
        right_key = cr.verify_record_signature(probe_payload, worker_pub)
        wrong_key = cr.verify_record_signature(probe_payload, op_pub)
        if not right_key or wrong_key:
            self._stage("KEYGEN").failed(
                "key_separation_failed",
                {"right_key_verified": right_key, "wrong_key_rejected": not wrong_key},
            )
            return
        # Schluessel-Dateien (Probe-Keys, NIE Betreiber-Keys)
        (self.workdir / "worker.key").write_text(worker_priv.hex(), encoding="utf-8")
        (self.workdir / "operator.key").write_text(op_priv.hex(), encoding="utf-8")
        keyring = {
            "public_keys": {"worker": worker_pub.hex(), "operator": op_pub.hex()},
            "expire_authorities": ["operator"],
        }
        (self.workdir / "keyring.json").write_text(json.dumps(keyring), encoding="utf-8")
        self._stage("KEYGEN").passed(
            {"keypairs_generated": 2, "wrong_key_rejected": True, "files": ["worker.key", "operator.key", "keyring.json"]}
        )

    def stage_lifecycle(self) -> Dict[str, Any]:
        ledger = self.workdir / "probe-ledger.jsonl"
        kr = self.workdir / "keyring.json"
        wk = self.workdir / "worker.key"
        r_claim = _run_cli(
            [
                "claim", "--ledger", ledger, "--keyring", kr, "--key", wk,
                "--author", "worker", "--task-id", "PROBE-1", "--scope", "probe/lifecycle",
                "--issued-at", self.now, "--base-sha", BASE_SHA, "--ttl-seconds", 3600,
            ]
        )
        if r_claim["exit"] != 0 or r_claim["payload"].get("status") != "ACCEPTED":
            self._stage("LIFECYCLE").failed("claim_refused", {"cli": r_claim["payload"], "exit": r_claim["exit"]})
            return {}
        r_status = _run_cli(["status", "--ledger", ledger, "--keyring", kr])
        active = r_status["payload"].get("active_claims", {})
        if r_status["exit"] != 0 or "PROBE-1" not in active:
            self._stage("LIFECYCLE").failed("status_missing_active_claim", {"cli": r_status["payload"]})
            return {}
        r_done = _run_cli(
            [
                "done", "--ledger", ledger, "--keyring", kr, "--key", wk,
                "--author", "worker", "--task-id", "PROBE-1", "--scope", "probe/lifecycle",
                "--sequence", 2, "--issued-at", self.now + 10,
            ]
        )
        if r_done["exit"] != 0:
            self._stage("LIFECYCLE").failed("done_refused", {"cli": r_done["payload"]})
            return {}
        reload = _run_cli(["status", "--ledger", ledger, "--keyring", kr])
        active_after = reload["payload"].get("active_claims", {})
        if "PROBE-1" in active_after or reload["exit"] != 0:
            self._stage("LIFECYCLE").failed("claim_still_active_after_done", {"cli": reload["payload"]})
            return {}
        self._stage("LIFECYCLE").passed(
            {"claim": "ACCEPTED", "status": "ACTIVE_SEEN", "done": "ACCEPTED", "freed_after_done": True}
        )
        return {"ledger": ledger, "keyring": kr, "worker_key": wk}

    def stage_watchdog(self, ctx: Dict[str, Any]) -> None:
        ledger = ctx["ledger"]
        kr = ctx["keyring"]
        op_key = self.workdir / "operator.key"
        r_claim = _run_cli(
            [
                "claim", "--ledger", ledger, "--keyring", kr, "--key", ctx["worker_key"],
                "--author", "worker", "--task-id", "PROBE-2", "--scope", "probe/watchdog",
                "--sequence", 3, "--issued-at", self.now, "--base-sha", BASE_SHA,
                "--ttl-seconds", 60,
            ]
        )
        if r_claim["exit"] != 0:
            self._stage("WATCHDOG").failed("watchdog_seed_claim_refused", {"cli": r_claim["payload"]})
            return
        before = ledger.read_bytes()
        r_scan = _run_cli(["scan", "--ledger", ledger, "--keyring", kr, "--now", self.now + 120])
        ids = [c.get("task_id") for c in r_scan["payload"].get("expired_claims", [])]
        writes = ledger.read_bytes()
        if r_scan["exit"] != 0 or ids != ["PROBE-2"]:
            self._stage("WATCHDOG").failed("scan_did_not_detect_due_claim", {"cli": r_scan["payload"]})
            return
        if writes != before:
            self._stage("WATCHDOG").failed("scan_wrote_bytes", {})
            return
        # Unautorisiertes expire muss verweigert werden und null Byte schreiben
        r_bad = _run_cli(
            [
                "expire", "--ledger", ledger, "--keyring", kr, "--key", ctx["worker_key"],
                "--author", "worker", "--reason", "unbefugt", "--now", self.now + 120,
            ]
        )
        if r_bad["exit"] != 2 or ledger.read_bytes() != before:
            self._stage("WATCHDOG").failed("unauthorized_expire_not_refused", {"cli": r_bad["payload"], "exit": r_bad["exit"]})
            return
        r_ok = _run_cli(
            [
                "expire", "--ledger", ledger, "--keyring", kr, "--key", op_key,
                "--author", "operator", "--reason", "Probe: ttl 60s ueberschritten", "--now", self.now + 120,
            ]
        )
        if r_ok["exit"] != 0 or r_ok["payload"].get("status") != "APPLIED":
            self._stage("WATCHDOG").failed("authorized_expire_failed", {"cli": r_ok["payload"]})
            return
        # Nach EXPIRE ist der scope wieder frei belegbar
        r_reclaim = _run_cli(
            [
                "claim", "--ledger", ledger, "--keyring", kr, "--key", ctx["worker_key"],
                "--author", "worker", "--task-id", "PROBE-3", "--scope", "probe/watchdog",
                "--sequence", 4, "--issued-at", self.now + 130, "--base-sha", BASE_SHA,
                "--ttl-seconds", 3600,
            ]
        )
        if r_reclaim["exit"] != 0:
            self._stage("WATCHDOG").failed("reclaim_after_expire_refused", {"cli": r_reclaim["payload"]})
            return
        self._stage("WATCHDOG").passed(
            {
                "scan_detected": ids,
                "scan_zero_byte": True,
                "unauthorized_expire_exit_2_zero_byte": True,
                "authorized_expire": "APPLIED",
                "reclaim_after_expire": "ACCEPTED",
            }
        )

    def stage_integrity(self, ctx: Dict[str, Any]) -> None:
        source = ctx["ledger"]
        corrupt = self.workdir / "corrupt-ledger.jsonl"
        raw = source.read_bytes()
        corrupt.write_bytes(raw[:-5])  # abgeschnittene letzte Zeile
        r = _run_cli(["scan", "--ledger", corrupt, "--keyring", ctx["keyring"]])
        if r["exit"] != 3 or r["payload"].get("status") != "CORRUPT_OR_INVALID":
            self._stage("INTEGRITY").failed("corrupt_ledger_not_exit_3", {"cli": r["payload"], "exit": r["exit"]})
            return
        self._stage("INTEGRITY").passed({"truncated_ledger_exit_3": True})


def run_probe(args: argparse.Namespace) -> int:
    started = int(time.time())

    missing = _has_real_ed25519()
    if missing is not None:
        report = {
            "probe": PROBE_NAME,
            "status": "REQUIREMENTS_MISSING",
            "backend": missing,
            "stages": [],
            "honesty": "STUB != ECHT: kein echter Ed25519-Nachweis moeglich; kein Schein-Report",
            "started_epoch": started,
            "finished_epoch": int(time.time()),
        }
        return _finish(report, args, EXIT_FAILED_OR_MISSING)

    tmp_parent = Path(tempfile.mkdtemp(prefix="v91-probe-", dir=str(args.workdir) if args.workdir else None))
    keep = bool(args.keep)
    try:
        probe = Probe(tmp_parent)
        probe.stage_keygen()
        ctx: Dict[str, Any] = {}
        if probe.stages and probe.stages[0].status == "PASS":
            ctx = probe.stage_lifecycle()
        if ctx:
            probe.stage_watchdog(ctx)
        if ctx:
            probe.stage_integrity(ctx)
        all_pass = all(s.status == "PASS" for s in probe.stages) and probe.stages
        status = "PROBE_PASSED" if all_pass else "PROBE_FAILED"
        report = {
            "probe": PROBE_NAME,
            "status": status,
            "tasks": {"claim_ledger": "exercised", "author_receipt_guard": "implied_via_ledger_signatures", "v91_claim_cli": "exercised", "v91_watchdog": "exercised"},
            "stages": [s.as_dict() for s in probe.stages],
            "probe_dir": str(tmp_parent),
            "probe_dir_kept": keep,
            "honesty": "PROBE != BETRIEB: Einmalige Kette im Sandbox-Ledger; KEIN Dauerbetriebsnachweis, KIT != INSTALLED",
            "started_epoch": started,
            "finished_epoch": int(time.time()),
        }
        code = EXIT_OK if all_pass else EXIT_FAILED_OR_MISSING
        return _finish(report, args, code, tmp_parent if keep else None)
    finally:
        if not keep:
            shutil.rmtree(tmp_parent, ignore_errors=True)


def _finish(report: Dict[str, Any], args: argparse.Namespace, code: int, keep_dir: Optional[Path] = None) -> int:
    if keep_dir is not None:
        report["probe_dir_kept"] = str(keep_dir)
    text = json.dumps(report, sort_keys=True, ensure_ascii=True)
    sys.stdout.write(text + chr(10))
    if args.report:
        try:
            target = Path(args.report)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text + chr(10), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write("report not writable: " + str(exc) + chr(10))
            return EXIT_IO
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROBE_NAME,
        description="Selbstaendiger E2E-Betriebsprobe-Kit fuer das V91-Claim-Ledger (fail-closed).",
    )
    parser.add_argument("--report", default=None, help="Maschinenlesbarer PROBE-Report (JSON-Datei) fuers Betreiber-Archiv")
    parser.add_argument("--keep", action="store_true", help="Probe-Verzeichnis NICHT loeschen (Beweissicherung)")
    parser.add_argument("--workdir", default=None, help="Basisverzeichnis fuer die temporaere Probe (Standard: Systemtemp)")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return run_probe(args)


if __name__ == "__main__":
    raise SystemExit(main())

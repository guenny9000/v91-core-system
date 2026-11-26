"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Alarm-Delivery-Guard (Issue #520-Rest, Anforderung 4): Offline-
pruefbare Versand-Sicherheitsstandards fuer den kuenftigen, getrennt
geprueften Alarm-Versand-Adapter. Bewusst KEIN Netz im Modulkern:
DNS-Aufloesung wird INJIZIERT (resolve_fn), damit Tests deterministisch
bleiben und der Kern keine Verbindung aufbaut (SCRIPTED != INSTALLED).

Vertrag (fail-closed):
- HTTPS-Pflicht, kein Userinfo im Ziel (Basis-Auth-Leak-Vermeidung),
  Ziel muss in der expliziten Betreiber-Allowlist stehen
  (REQUEST != AUTHORIZATION).
- SSRF-Schutz: JEDE aufgeloeste Adresse muss global-routbar sein;
  Loopback, private, link-lokale, reservierte, multicast- und
  nicht spezifizierte Adressen werden abgelehnt. Ein einziger
  boesartiger Treffer in der Menge verwirft die GESAMTE Aufloesung
  (DNS-Rebinding: TEILMENGE OK IST NICHT OK).
- Redirect-Ablehnung ist PFLICHT (kein opt-out).
- Strikte Timeouts: 0 < timeout_s <= 30; Payload-Limit <= 8192 Bytes.
- NICHT_AUFGELOEST != BESTANDEN: Fehler der Aufloesung oder fehlende
  Aufloesung ist UNKNOWN, niemals PASS (UNKNOWN != PASS).
- Der Guard ersetzt KEINE Autorisierung: ein bestandener Plan ist ein
  PLAN, kein Versand und keine Befugnis (PLAN != VERSANDT,
  PRUEFUNG != FREIGABE).

Ehrliche Grenzen:
- Kein echter Versand, kein Netzwerk, kein Daemon.
- Guards pruefen PLAN-Daten; zur Laufzeit muss der Adapter erneut
  pruefen (TOCTOU: Aufloesungen koennen sich aendern,
  PRUEFUNG != GEOFORT).
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

MAX_PAYLOAD_BYTES = 8192
MAX_TIMEOUT_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 10

class DeliveryGuardError(RuntimeError):
    """Versand-Plan verletzt einen Sicherheitsstandard (fail-closed)."""


def pruefe_ziel(ziel: Any, allowlist: List[str]) -> str:
    """Ziel-URL-Pruefung: HTTPS, kein Userinfo, Host in Allowlist."""
    if not isinstance(ziel, str) or not ziel.strip():
        raise DeliveryGuardError("ziel must be a non-empty https URL string")
    parsed = urllib.parse.urlsplit(ziel.strip())
    if parsed.scheme.lower() != "https":
        raise DeliveryGuardError(f"only https destinations are plannable: {ziel!r}")
    if parsed.username or parsed.password:
        raise DeliveryGuardError("userinfo in destination URL is rejected (credential leak)")
    if not parsed.hostname:
        raise DeliveryGuardError("destination URL has no host")
    if not isinstance(allowlist, list) or not allowlist:
        raise DeliveryGuardError(
            "delivery is disabled by default: an explicit operator allowlist is required"
        )
    if ziel.strip() not in allowlist:
        raise DeliveryGuardError(f"destination {ziel!r} is not in the operator allowlist")
    return ziel.strip()


def pruefe_adressen(adressen: Any) -> List[str]:
    """SSRF-Pruefung: JEDE Adresse muss global-routbar sein (fail-closed)."""
    if not isinstance(adressen, list) or not adressen:
        raise DeliveryGuardError("resolved address list must be non-empty")
    geprueft: List[str] = []
    for addr in adressen:
        if not isinstance(addr, str) or not addr.strip():
            raise DeliveryGuardError("resolved addresses must be non-empty strings")
        try:
            ip = ipaddress.ip_address(addr.strip())
        except ValueError as exc:
            raise DeliveryGuardError(f"unparseable resolved address {addr!r} (fail-closed)") from exc
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
            or not ip.is_global
        ):
            raise DeliveryGuardError(
                f"SSRF guard: non-global address {addr!r} rejected "
                "(loopback/private/link-local/reserved/multicast; DNS rebinding: one bad address fails all)"
            )
        geprueft.append(str(ip))
    return geprueft


def pruefe_grenzen(config: Dict[str, Any]) -> Dict[str, Any]:
    """Strikte Plan-Grenzen: Redirect-Ablehnung Pflicht, Timeout/Payload begrenzt."""
    if not isinstance(config, dict):
        raise DeliveryGuardError("config must be an object")
    redirect = config.get("redirect_ablehnung", True)
    if redirect is not True:
        raise DeliveryGuardError("redirect rejection is mandatory and cannot be disabled")
    timeout = config.get("timeout_s", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise DeliveryGuardError("timeout_s must be a number")
    if not 0 < float(timeout) <= MAX_TIMEOUT_SECONDS:
        raise DeliveryGuardError(f"timeout_s must lie in (0, {MAX_TIMEOUT_SECONDS}] (strict timeouts)")
    limit = config.get("payload_limit_bytes", MAX_PAYLOAD_BYTES)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise DeliveryGuardError("payload_limit_bytes must be an integer")
    if not 0 < limit <= MAX_PAYLOAD_BYTES:
        raise DeliveryGuardError(f"payload_limit_bytes must lie in (0, {MAX_PAYLOAD_BYTES}]")
    return {
        "redirect_ablehnung": True,
        "timeout_s": timeout,
        "payload_limit_bytes": limit,
    }


def bewerte_aufloesung(
    config: Dict[str, Any],
    resolve_fn: Optional[Callable[[str], List[str]]] = None,
) -> Dict[str, Any]:
    """Aufloesungs-Bewertung: injizierter Resolver, NICHT_AUFGELOEST != BESTANDEN."""
    host = urllib.parse.urlsplit(str(config.get("ziel", ""))).hostname
    if resolve_fn is None:
        return {"aufloesung": "NICHT_GEPRUEFT", "adressen": []}
    if not host:
        raise DeliveryGuardError("ziel has no host to resolve")
    try:
        adressen = resolve_fn(host)
    except Exception as exc:  # Resolver-Fehler ist fail-closed, kein Durchwischen
        raise DeliveryGuardError(f"destination resolution failed (fail-closed): {exc}") from exc
    geprueft = pruefe_adressen(adressen)
    return {"aufloesung": "PRUEFUNG_BESTANDEN", "adressen": geprueft}


def bewerte_plan(
    config: Dict[str, Any],
    resolve_fn: Optional[Callable[[str], List[str]]] = None,
) -> Dict[str, Any]:
    """Vollstaendige Plan-Bewertung (kein Netz, kein Versand)."""
    ziel = pruefe_ziel(config.get("ziel"), config.get("destination_allowlist", []))
    grenzen = pruefe_grenzen(config)
    aufloesung = bewerte_aufloesung({**config, "ziel": ziel}, resolve_fn)
    return {
        "ziel": ziel,
        "verwendung": "PLAN",
        **grenzen,
        **aufloesung,
        "hinweis": "PLAN != VERSANDT: Ausfuehrung benoetigt einen getrennt geprueften Adapter",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Alarm-Delivery-Guard (Issue #520, offline, kein Versand)")
    parser.add_argument("--self-check", action="store_true", help="synthetic fixture self-check (SYNTHETISCH != MESSUNG)")
    args = parser.parse_args(argv)
    if not args.self_check:
        print("usage: --self-check", file=sys.stderr)
        return 2
    allowlist = ["https://ops.example/warnungen"]
    gut = bewerte_plan(
        {"ziel": "https://ops.example/warnungen", "destination_allowlist": allowlist,
         "timeout_s": 5, "payload_limit_bytes": 4096},
        resolve_fn=lambda host: ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:19e6"],
    )
    rebinding = False
    try:
        bewerte_plan(
            {"ziel": "https://ops.example/warnungen", "destination_allowlist": allowlist},
            resolve_fn=lambda host: ["203.0.113.10", "192.168.0.5"],
        )
    except DeliveryGuardError:
        rebinding = True
    ohne_resolver = bewerte_plan({"ziel": "https://ops.example/warnungen", "destination_allowlist": allowlist})
    ok = (
        gut["aufloesung"] == "PRUEFUNG_BESTANDEN"
        and gut["redirect_ablehnung"] is True
        and gut["timeout_s"] == 5
        and gut["payload_limit_bytes"] == 4096
        and rebinding
        and ohne_resolver["aufloesung"] == "NICHT_GEPRUEFT"
    )
    print(json.dumps({
        "mechanismus": "getestet",
        "reale_auslieferung": "NICHT_GEPRUEFT",
        "self_check": "PASS" if ok else "FEHLER",
        "rebinding_abgewiesen": rebinding,
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

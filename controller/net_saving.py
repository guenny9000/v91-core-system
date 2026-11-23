#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Deterministic net-saving accounting with explicit lifecycle costs
(V91-RESOURCE-SAVINGS-VERIFICATION-PROTOCOL.md, section 5).

The result is a CALCULATED CANDIDATE only. A positive net value is
never proof of real-world causation and is never INDEPENDENTLY_VERIFIED
(protocol section 6: independent verification requires a separate
reviewer and cannot be self-assigned by a calculation).

Fail-closed rules enforced here:
- every term must be a finite plain number (bool is rejected);
- costs must be non-negative (UNKNOWN is never imputed as zero);
- the currency and time horizon of the total must be stated;
- unknown cost keys are rejected (typos would silently reduce costs);
- a single currency is enforced per record - no mixing.
"""

import math

GROSS_TERM = "gross_monetary_benefit"
META_KEYS = frozenset({"currency", "horizon", "price_basis", "notes"
                       , "extrapolated_from"})
ALLOWED_COST_TERMS = (
    "implementation_cost",
    "migration_cost",
    "operating_cost_delta",
    "maintenance_cost_delta",
    "training_cost",
    "financing_cost",
    "disposal_cost",
    "other_material_cost",
)


class NetSavingError(ValueError):
    """Raised when an accounting record is not admissible."""


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NetSavingError(
            label + ": not a number (UNKNOWN must never be imputed as zero)")
    value_f = float(value)
    if not math.isfinite(value_f):
        raise NetSavingError(label + ": value is not finite")
    return value_f


def compute_net_saving(terms):
    """Deterministic net-saving calculation per protocol section 5.

    terms: dict with gross_monetary_benefit, currency, horizon and
    any subset of ALLOWED_COST_TERMS. Returns a candidate record that
    is explicitly separated from independent verification.
    """
    if not isinstance(terms, dict):
        raise NetSavingError("terms: dict required")

    currency = terms.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise NetSavingError(
            "currency: required so physical units never enter a"
            " monetary total")
    horizon = terms.get("horizon")
    if not isinstance(horizon, str) or not horizon.strip():
        raise NetSavingError(
            "horizon: the shared time horizon of all terms must be stated")

    gross = _finite_number(terms.get(GROSS_TERM), GROSS_TERM)

    cost_terms = {}
    unknown = []
    for key in terms:
        if key == GROSS_TERM or key in META_KEYS:
            continue
        if key not in ALLOWED_COST_TERMS:
            unknown.append(key)
            continue
        amount = _finite_number(terms[key], key)
        if amount < 0:
            raise NetSavingError(key + ": costs must be non-negative")
        cost_terms[key] = amount
    if unknown:
        raise NetSavingError(
            "unknown cost terms (typos would silently reduce costs and"
            " invent savings): " + ", ".join(sorted(unknown)))

    total_costs = math.fsum(cost_terms.values())
    net = gross - total_costs
    if net > 0:
        candidate = "NET_POSITIVE_CANDIDATE"
    elif net == 0:
        candidate = "NET_ZERO_CANDIDATE"
    else:
        candidate = "NET_NEGATIVE_CANDIDATE"

    return {
        "currency": currency.strip(),
        "horizon": horizon.strip(),
        "gross_monetary_benefit": round(gross, 6),
        "cost_terms": cost_terms,
        "total_lifecycle_costs": round(total_costs, 6),
        "net_saving": round(net, 6),
        "candidate_status": candidate,
        "attribution": "CALCULATED_ONLY",
        "review_status": "NOT_INDEPENDENTLY_VERIFIED",
    }

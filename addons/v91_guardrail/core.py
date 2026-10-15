"""Read-only policy evaluation. No network, filesystem, subprocess, or model calls."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class PolicyContext:
    # Caller-provided declarations; this module does not independently verify them.
    source_is_authorized: bool = False
    human_approved: bool = False
    allow_read_only_analysis: bool = True
    network_requested: bool = False
    destructive_action_requested: bool = False
    privilege_change_requested: bool = False
    execute_code_requested: bool = False
    private_data_requested: bool = False


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[str, ...]
    topic_flags: tuple[str, ...]
    evidence_state: str
    action_performed: bool = False

    def to_dict(self) -> dict:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["topic_flags"] = list(self.topic_flags)
        return result


TOPIC_PATTERNS = {
    "CONFLICT_OR_WAR": re.compile(
        r"\b(krieg|bewaffnet(?:e|er|en)? konflikt|waffenhandel|"
        r"militärangriff|munitionsproduktion|rüstungsindustrie|frontverlauf)\b", re.I
    ),
    "RESOURCE_OR_ENVIRONMENT": re.compile(
        r"\b(entropie|energieverbrauch|co2|emissionen|ressourcenverbrauch|"
        r"abfall|verschwendung|überproduktion|reparatur|recycling|"
        r"lebenszyklus|wasserverbrauch)\b", re.I
    ),
    "LUXURY_OR_NONESSENTIAL_PRODUCTION": re.compile(
        r"\b(luxusüberproduktion|luxusgüter|nicht notwendige überproduktion|"
        r"geplante obsoleszenz|wegwerfprodukt|überflüssige produktion)\b", re.I
    ),
    "CYBER_OR_SYSTEM_ACTION": re.compile(
        r"\b(exploit|schwachstelle ausnutzen|passwort stehlen|"
        r"zugangsdaten abgreifen|malware|ransomware|fernsteuerung)\b", re.I
    ),
}

HIGH_RISK_PATTERNS = {
    "DESTRUCTIVE_ACTION_CUE": re.compile(
        r"\b(lösche|löschen|vernichte|wipe|purge|formatier(?:e|en))\b", re.I
    ),
    "EXECUTION_CUE": re.compile(
        r"\b(führe aus|execute|shell-befehl|powershell|cmd\.exe)\b", re.I
    ),
    "PRIVILEGE_ESCALATION_CUE": re.compile(
        r"\b(adminrechte|rechteausweitung|privilegien erhöhen|root-zugriff)\b", re.I
    ),
    "UNAUTHORIZED_ACCESS_CUE": re.compile(
        r"\b(hacke|unbefugter zugriff|umgehe die anmeldung|zugriff umgehen)\b", re.I
    ),
}


def evaluate(text: str, *, context: PolicyContext | None = None) -> Decision:
    """Evaluate a proposal; never perform the proposed action."""
    context = context or PolicyContext()
    if not isinstance(text, str) or not text.strip():
        return Decision("BLOCK", ("EMPTY_OR_INVALID_REQUEST",), (), "NO_DATA_AVAILABLE")

    topic_flags = tuple(sorted(
        name for name, pattern in TOPIC_PATTERNS.items() if pattern.search(text)
    ))
    risk_cues = sorted(
        name for name, pattern in HIGH_RISK_PATTERNS.items() if pattern.search(text)
    )
    reasons: list[str] = []

    if context.private_data_requested:
        reasons.append("PRIVATE_DATA_REQUEST_BLOCKED")
    if context.network_requested and not context.source_is_authorized:
        reasons.append("NETWORK_ACCESS_NOT_AUTHORIZED")
    if context.destructive_action_requested and not context.human_approved:
        reasons.append("DESTRUCTIVE_ACTION_REQUIRES_SEPARATE_APPROVAL")
    if context.privilege_change_requested:
        reasons.append("PRIVILEGE_CHANGE_NOT_ALLOWED_BY_DEFAULT")
    if context.execute_code_requested and not context.human_approved:
        reasons.append("CODE_EXECUTION_REQUIRES_SEPARATE_APPROVAL")
    reasons.extend("HIGH_RISK_CUE:" + cue for cue in risk_cues)

    if reasons:
        return Decision("BLOCK", tuple(reasons), topic_flags, "DOCUMENTED_INPUT_ONLY")
    if topic_flags:
        return Decision(
            "REVIEW_REQUIRED",
            ("TOPIC_FLAG_IS_NOT_A_FACT_FINDING", "NO_EXTERNAL_EVIDENCE_FETCHED"),
            topic_flags,
            "PENDING_WITNESS",
        )
    if not context.allow_read_only_analysis:
        return Decision("BLOCK", ("READ_ONLY_ANALYSIS_NOT_ALLOWED",), (), "DOCUMENTED_INPUT_ONLY")

    return Decision(
        "ALLOW_LOCAL_REVIEW",
        ("NO_LOCAL_POLICY_BLOCK_FOUND", "ALLOW_IS_NOT_A_SECURITY_GUARANTEE"),
        (),
        "DOCUMENTED_INPUT_ONLY",
    )


def evaluate_batch(
    proposals: Iterable[str], *, context: PolicyContext | None = None
) -> list[Decision]:
    """Evaluate proposals using the same caller-declared context."""
    return [evaluate(proposal, context=context) for proposal in proposals]

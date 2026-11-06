"""V99 einheitliche Statuswerte (Reality-First).

UNKNOWN darf niemals automatisch als HEALTHY behandelt werden.
"""
from enum import Enum


class Status(str, Enum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    ISOLATED = "ISOLATED"
    RECOVERING = "RECOVERING"
    VERIFIED = "VERIFIED"


VALID_STATUSES = frozenset(s.value for s in Status)

# Niveau fuer aggregierte Berichte: unbekannt ist nie "gesund".
_AGGREGATE_ORDER = [
    Status.VERIFIED.value,
    Status.HEALTHY.value,
    Status.RECOVERING.value,
    Status.DEGRADED.value,
    Status.UNKNOWN.value,
    Status.ISOLATED.value,
    Status.FAILED.value,
]


def aggregate_status(statuses) -> str:
    """Aggregiert mehrere Statuswerte; UNKNOWN schlaegt HEALTHY, FAILED schlaegt UNKNOWN."""
    values = [s if isinstance(s, str) else Status(s).value for s in statuses]
    for level in reversed(_AGGREGATE_ORDER):
        if level in values:
            return level
    return Status.UNKNOWN.value

"""V99 Scheduler (Phase 2): zeitgesteuerte Pruefzyklen, deterministisch testbar.

Kein Netzwerk, keine Threads, kein Daemon: Der Scheduler entscheidet nur,
OB ein Zyklus faellig ist, und fuehrt ihn kontrolliert aus. Dauerbetrieb
ueber OS-Dienste (systemd/launchd/Taskplaner) folgt in Phase 6 – ein
sleep()-Loop waere nur ein behaupteter, kein belegter Ewigbetrieb.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from v99.core.status import Status, aggregate_status

MAX_HISTORY = 100


@dataclass(frozen=True)
class CycleResult:
    started_at: str
    finished_at: str
    aggregate: str
    module_statuses: dict
    proposals: int
    executed: tuple


class CycleScheduler:
    def __init__(self, agent, interval_seconds: int = 900,
                 clock: Optional[Callable[[], datetime]] = None,
                 stop_check: Optional[Callable[[], tuple]] = None):
        if not isinstance(interval_seconds, int) or interval_seconds < 1:
            raise ValueError("interval_seconds muss eine positive Ganzzahl sein")
        if stop_check is not None and not callable(stop_check):
            raise TypeError("stop_check muss callable sein oder None")
        self.agent = agent
        self.interval_seconds = interval_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop_check = stop_check
        self.history: list = []
        self._last_run: Optional[datetime] = None

    def now(self) -> datetime:
        moment = self._clock()
        if moment.tzinfo is None:
            raise ValueError("Clock muss zeitzonenbewusste Zeit liefern")
        return moment

    def missed_intervals(self) -> int:
        """Wie viele Pruefzyklen seit dem letzten Lauf verstrichen sind."""
        if self._last_run is None:
            return 0
        elapsed = (self.now() - self._last_run).total_seconds()
        return max(0, int(elapsed // self.interval_seconds))

    def due(self) -> bool:
        if self._last_run is None:
            return True
        return (self.now() - self._last_run).total_seconds() >= self.interval_seconds

    def run_cycle(self) -> CycleResult:
        """Ein kontrollierter Zyklus: inspizieren -> vorschlagen -> nur sichere Reparaturen."""
        started = self.now().isoformat()
        if self._stop_check is not None:
            stopped, reason = self._stop_check()
            if stopped:
                # Notaus: kein inspect, kein Vorschlag, keine Ausfuehrung.
                result = CycleResult(
                    started_at=started,
                    finished_at=self.now().isoformat(),
                    aggregate="HALTED",
                    module_statuses={},
                    proposals=0,
                    executed=(),
                )
                self.history.append(result)
                if len(self.history) > MAX_HISTORY:
                    self.history = self.history[-MAX_HISTORY:]
                self._last_run = self.now()
                return result
        reports = self.agent.inspect_all()
        proposals = self.agent.prepare_repairs()
        executed = ()
        if proposals:
            executed = tuple(self.agent.execute_safe_repairs(proposals))
        if reports:
            aggregate = aggregate_status(
                r.status.value if isinstance(r.status, Status) else r.status
                for r in reports
            )
        else:
            aggregate = Status.UNKNOWN.value  # keine Module != alles gesund
        finished = self.now().isoformat()
        result = CycleResult(
            started_at=started,
            finished_at=finished,
            aggregate=aggregate,
            module_statuses={r.module_id: (r.status.value if isinstance(r.status, Status) else str(r.status)) for r in reports},
            proposals=len(proposals),
            executed=executed,
        )
        self.history.append(result)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self._last_run = self.now()
        return result

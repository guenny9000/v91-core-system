"""V99 Lifecycle-Steuerung (Phase 2): erzwungene, gueltige Zustandsuebergaenge.

Fail-closed: ungueltige Uebergaenge werden verweigert, HALTED ist absorbierend
(nur explizites reset() verlaesst es). Kein Modul kann den Zustand des
Gesamtsystems eigenmaechtig manipulieren.
"""
from enum import Enum


class LifecycleState(str, Enum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HALTED = "HALTED"


_ALLOWED = {
    LifecycleState.INITIALIZING: {LifecycleState.RUNNING, LifecycleState.HALTED},
    LifecycleState.RUNNING: {LifecycleState.PAUSED, LifecycleState.HALTED},
    LifecycleState.PAUSED: {LifecycleState.RUNNING, LifecycleState.HALTED},
    LifecycleState.HALTED: set(),
}


class LifecycleStateMachine:
    def __init__(self):
        self._state = LifecycleState.INITIALIZING

    @property
    def state(self) -> LifecycleState:
        return self._state

    def transition(self, new_state: LifecycleState) -> LifecycleState:
        if not isinstance(new_state, LifecycleState):
            raise TypeError("new_state muss ein LifecycleState sein")
        if new_state not in _ALLOWED[self._state]:
            raise ValueError(f"Uebergang {self._state.value} -> {new_state.value} ist nicht erlaubt")
        self._state = new_state
        return self._state

    def reset(self) -> LifecycleState:
        """Expliziter, bewusster Neustart – HALTED verlaesst man nie 'nebenbei'."""
        self._state = LifecycleState.INITIALIZING
        return self._state

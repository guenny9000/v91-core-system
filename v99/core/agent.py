"""V99 Agent-Kern: pruefen, vorschlagen, kontrolliert ausfuehren.

Korrekturen gegenueber dem Chatab-Entwurf:
- __init__ statt _init_ (Tippfehler im Entwurf).
- Inspektionsfehler erzeugen UNKNOWN, nie HEALTHY.
- Identitaetsabweichungen (Report/Proposal gehoert zu anderem Modul)
  werden verworfen bzw. als UNKNOWN gemeldet.
- Erkennen, Pruefen, Freigeben und Ausfuehren sind getrennte Vorgaenge.
Kein Scheduler, keine Persistenz, keine Netzwerkzugriffe: Phase-1-Kern.
"""
from dataclasses import dataclass

from v99.core.status import Status
from v99.core.registry import ModuleRegistry


@dataclass(frozen=True)
class ModuleReport:
    module_id: str
    version: str
    status: Status
    details: str = ""


@dataclass(frozen=True)
class ActionProposal:
    module_id: str
    action: str
    reason: str
    reversible: bool
    requires_approval: bool = True


class PolicyEngine:
    """Stufe 3/4: nur reversible, vorher freigegebene Aktionen sind erlaubt."""

    @staticmethod
    def allowed(proposal: ActionProposal) -> bool:
        if not proposal.reversible:
            return False
        if proposal.requires_approval:
            return False
        return True


class V99Agent:
    def __init__(self, registry: ModuleRegistry, policy=None):
        self.registry = registry
        self.policy = policy or PolicyEngine()

    def inspect_all(self) -> list:
        reports = []
        for module_id in self.registry.list_module_ids():
            adapter = self.registry.get_adapter(module_id)
            spec = self.registry.get_spec(module_id)
            if adapter is None:
                reports.append(ModuleReport(module_id, spec.version, Status.UNKNOWN,
                                            "Kein Adapter registriert"))
                continue
            try:
                report = adapter.inspect()
                if report.module_id != module_id:
                    reports.append(ModuleReport(module_id, spec.version, Status.UNKNOWN,
                                                f"Identitaetsabweichung: gemeldet '{report.module_id}'"))
                    continue
                reports.append(report)
            except Exception as exc:  # noqa: BLE001 - Fehler wird berichtet, nie als Erfolg gewertet
                reports.append(ModuleReport(module_id, spec.version, Status.UNKNOWN,
                                            f"Inspektion fehlgeschlagen: {exc}"))
        return reports

    def prepare_repairs(self) -> list:
        proposals = []
        for module_id in self.registry.list_module_ids():
            adapter = self.registry.get_adapter(module_id)
            if adapter is None:
                continue
            try:
                proposal = adapter.propose_repair()
            except Exception:  # noqa: BLE001 - Vorschlagsphase darf nie den Agent abstuerzen lassen
                continue
            if proposal is None:
                continue
            if proposal.module_id != module_id:
                continue
            proposals.append(proposal)
        return proposals

    def execute_safe_repairs(self, proposals) -> list:
        results = []
        for proposal in proposals:
            if not self.policy.allowed(proposal):
                results.append((proposal.module_id, "NOT_AUTHORIZED"))
                continue
            adapter = self.registry.get_adapter(proposal.module_id)
            if adapter is None:
                results.append((proposal.module_id, "NO_ADAPTER"))
                continue
            try:
                success = adapter.execute(proposal)
                results.append((proposal.module_id, "SUCCESS" if success else "FAILED"))
            except Exception as exc:  # noqa: BLE001
                results.append((proposal.module_id, f"FAILED: {exc}"))
        return results

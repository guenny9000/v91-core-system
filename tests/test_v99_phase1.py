"""V99 Phase-1-Regressionstests (Reality-First, nur stdlib)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v99.core.agent import ActionProposal, ModuleReport, PolicyEngine, V99Agent
from v99.core.module_standard import load_module_spec
from v99.core.registry import ModuleRegistry
from v99.core.status import Status, aggregate_status
from v99.security.key_rotation import rotate_key


def spec_dict(module_id="m1", permissions=("read_module_status",)):
    return {
        "module_id": module_id,
        "name": "Modul " + module_id,
        "version": "0.1.0",
        "api_version": "1",
        "enabled": True,
        "platforms": ["windows", "linux"],
        "capabilities": ["health_check"],
        "permissions": list(permissions),
        "healthcheck": {"enabled": True, "interval_seconds": 300},
        "update_policy": {"automatic_check": True, "automatic_install": False,
                          "rollback_required": True},
    }


class StaticAdapter:
    def __init__(self, module_id, status=Status.HEALTHY, proposal=None, execute_ok=True):
        self.module_id = module_id
        self.status = status
        self.proposal = proposal
        self.execute_ok = execute_ok
        self.executed = []

    def inspect(self):
        return ModuleReport(self.module_id, "0.1.0", self.status, "ok")

    def propose_repair(self):
        return self.proposal

    def execute(self, proposal):
        self.executed.append(proposal)
        return self.execute_ok


class FailingAdapter(StaticAdapter):
    def inspect(self):
        raise RuntimeError("boom")

    def propose_repair(self):
        raise RuntimeError("boom")


class TestModuleStandard(unittest.TestCase):
    def test_valid_spec_loads(self):
        spec = load_module_spec(spec_dict())
        self.assertEqual(spec.module_id, "m1")
        self.assertEqual(spec.healthcheck.interval_seconds, 300)

    def test_missing_field_fails_closed(self):
        data = spec_dict()
        del data["version"]
        with self.assertRaises(ValueError):
            load_module_spec(data)

    def test_wrong_type_fails_closed(self):
        data = spec_dict()
        data["enabled"] = "yes"
        with self.assertRaises(ValueError):
            load_module_spec(data)

    def test_bad_healthcheck_fails_closed(self):
        data = spec_dict()
        data["healthcheck"] = {"enabled": True, "interval_seconds": 0}
        with self.assertRaises(ValueError):
            load_module_spec(data)


class TestRegistry(unittest.TestCase):
    def test_duplicate_registration_rejected(self):
        reg = ModuleRegistry()
        reg.register(load_module_spec(spec_dict()))
        with self.assertRaises(ValueError):
            reg.register(load_module_spec(spec_dict()))

    def test_self_granted_permission_rejected(self):
        reg = ModuleRegistry()
        with self.assertRaises(PermissionError):
            reg.register(load_module_spec(spec_dict(permissions=("write_module_status",))))

    def test_listing_and_length(self):
        reg = ModuleRegistry()
        reg.register(load_module_spec(spec_dict("a")))
        reg.register(load_module_spec(spec_dict("b")))
        self.assertEqual(reg.list_module_ids(), ["a", "b"])
        self.assertEqual(len(reg), 2)


class TestAgent(unittest.TestCase):
    def _agent_with(self, adapters):
        reg = ModuleRegistry()
        for mid, adapter in adapters.items():
            reg.register(load_module_spec(spec_dict(mid)), adapter)
        return V99Agent(reg)

    def test_inspection_failure_is_unknown_never_healthy(self):
        agent = self._agent_with({"m1": FailingAdapter("m1")})
        reports = agent.inspect_all()
        self.assertEqual(reports[0].status, Status.UNKNOWN)

    def test_identity_mismatch_reported_as_unknown(self):
        class WrongId(StaticAdapter):
            def inspect(self):
                return ModuleReport("anderes-modul", "0.1.0", Status.HEALTHY)

        agent = self._agent_with({"m1": WrongId("m1")})
        self.assertEqual(agent.inspect_all()[0].status, Status.UNKNOWN)

    def test_irreversible_proposal_not_authorized(self):
        p = ActionProposal("m1", "delete_history", "cleanup", reversible=False)
        self.assertFalse(PolicyEngine.allowed(p))

    def test_approval_required_proposal_not_authorized(self):
        p = ActionProposal("m1", "restart_worker", "restart", reversible=True,
                           requires_approval=True)
        self.assertFalse(PolicyEngine.allowed(p))

    def test_only_safe_repair_executed(self):
        approved = ActionProposal("m1", "restart_worker", "restart", reversible=True,
                                  requires_approval=False)
        blocked = ActionProposal("m1", "drop_data", "cleanup", reversible=False)
        adapter = StaticAdapter("m1", proposal=approved)
        agent = self._agent_with({"m1": adapter})
        results = agent.execute_safe_repairs([approved, blocked])
        self.assertEqual(results, [("m1", "SUCCESS"), ("m1", "NOT_AUTHORIZED")])
        self.assertEqual([p.action for p in adapter.executed], ["restart_worker"])

    def test_proposal_with_wrong_identity_discarded(self):
        wrong = ActionProposal("anderes-modul", "restart_worker", "restart", True, False)
        adapter = StaticAdapter("m1", proposal=wrong)
        agent = self._agent_with({"m1": adapter})
        self.assertEqual(agent.prepare_repairs(), [])


class TestStatusAggregation(unittest.TestCase):
    def test_unknown_never_aggregates_to_healthy(self):
        self.assertEqual(aggregate_status(["HEALTHY", "UNKNOWN"]), "UNKNOWN")

    def test_failed_beats_unknown(self):
        self.assertEqual(aggregate_status(["UNKNOWN", "FAILED"]), "FAILED")

    def test_empty_is_unknown(self):
        self.assertEqual(aggregate_status([]), "UNKNOWN")


class FakeProvider:
    def __init__(self, healthy=True, created="new-secret", valid=True, revoke_ok=True):
        self.healthy = healthy
        self.created = created
        self.valid = valid
        self.revoke_ok = revoke_ok
        self.revoked = False

    def check_status(self):
        return "HEALTHY" if self.healthy else "DEGRADED"

    def create_replacement(self):
        return self.created

    def validate(self, secret):
        return self.valid and secret == self.created

    def revoke_old(self):
        self.revoked = True
        return self.revoke_ok


class FakeStore:
    def __init__(self, activate_ok=True):
        self.activate_ok = activate_ok
        self.stored = {}

    def store(self, name, value):
        self.stored[name] = value

    def activate(self, name):
        return self.activate_ok and name in self.stored


class TestKeyRotation(unittest.TestCase):
    def test_not_approved_does_nothing(self):
        provider, store = FakeProvider(), FakeStore()
        self.assertEqual(rotate_key(provider, store, "api"), "APPROVAL_REQUIRED")
        self.assertEqual(store.stored, {})
        self.assertFalse(provider.revoked)

    def test_unhealthy_provider_blocked(self):
        provider, store = FakeProvider(healthy=False), FakeStore()
        self.assertEqual(rotate_key(provider, store, "api", approved=True),
                         "PROVIDER_NOT_HEALTHY")
        self.assertFalse(provider.revoked)

    def test_activation_failure_keeps_old_key(self):
        provider, store = FakeProvider(), FakeStore(activate_ok=False)
        self.assertEqual(rotate_key(provider, store, "api", approved=True),
                         "ACTIVATION_FAILED_OLD_KEY_RETAINED")
        self.assertFalse(provider.revoked)

    def test_successful_rotation_revokes_old_last(self):
        provider, store = FakeProvider(), FakeStore()
        self.assertEqual(rotate_key(provider, store, "api", approved=True),
                         "ROTATION_SUCCESSFUL")
        self.assertTrue(provider.revoked)

    def test_invalid_secret_name_rejected(self):
        self.assertEqual(rotate_key(FakeProvider(), FakeStore(), ""), "INVALID_SECRET_NAME")


if __name__ == "__main__":
    unittest.main()

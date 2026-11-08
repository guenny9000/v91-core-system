import pytest

from controller.resource_admission import (
    AdmissionError,
    AdmissionRequest,
    HostResourceAdapter,
    ResourceAdmissionGate,
    ResourceMeasurements,
)

VERDICT_ALLOWED = 'ALLOWED_LOCAL'
VERDICT_DENIED = 'DENIED_LOCAL'


class FakeAdapter:
    def __init__(self, clock, values):
        self._clock = clock
        self._values = values

    def measure(self):
        values = dict(self._values)
        # Honor a pre-set measured_at so a stale snapshot stays stale;
        # only stamp the clock when the fixture did not inject one.
        values.setdefault('measured_at', self._clock())
        return ResourceMeasurements(**values)


@pytest.fixture
def clock():
    state = {'now': 1000.0}
    return lambda: state['now']


def make_gate(clock, values, **overrides):
    adapter = FakeAdapter(clock, values)
    params = {'adapter': adapter, 'clock': clock, 'freshness_seconds': 30}
    params.update(overrides)
    return ResourceAdmissionGate(**params)


GOOD = {'cpu_cores': 8.0, 'ram_mb': 16000, 'vram_mb': None, 'disk_mb': 500000}


def test_sufficient_fresh_measurement_is_admitted(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=8000, disk_mb=1000))
    assert decision.verdict == VERDICT_ALLOWED
    assert decision.measurements is not None


def test_missing_ram_is_never_unlimited(clock):
    gate = make_gate(clock, {**GOOD, 'ram_mb': None})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=8000))
    assert decision.verdict == VERDICT_DENIED
    assert 'NO_CAPACITY' in decision.reason


def test_vram_required_but_never_measured_is_denied(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=8000, vram_mb=4000))
    assert decision.verdict == VERDICT_DENIED
    assert 'UNKNOWN is never unlimited' in decision.reason


def test_stale_measurement_is_denied(clock):
    gate = make_gate(clock, GOOD)
    gate._adapter._values['measured_at'] = 900.0
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=8000))
    assert decision.verdict == VERDICT_DENIED
    assert 'Stale measurement' in decision.reason


def test_insufficient_cpu_is_denied_with_deficit(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=16, ram_mb=8000))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores 16.0 > 8.0' in decision.reason


def test_insufficient_ram_is_denied(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=32000))
    assert decision.verdict == VERDICT_DENIED
    assert 'ram_mb 32000 > 16000' in decision.reason


def test_quota_bounds_admission(clock):
    gate = make_gate(clock, GOOD, quota={'cpu_cores': 4, 'ram_mb': 8000})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=2, ram_mb=4000))
    assert decision.verdict == VERDICT_DENIED
    assert 'quota' in decision.reason


def test_malformed_request_is_denied(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=0, ram_mb=-5))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores' in decision.reason


def test_admission_is_deterministic_for_same_inputs(clock):
    gate = make_gate(clock, GOOD)
    r = AdmissionRequest(cpu_cores=4, ram_mb=8000)
    assert gate.request_admission(r).verdict == gate.request_admission(r).verdict


def test_gate_rejects_bad_constructor_args(clock):
    adapter = FakeAdapter(clock, GOOD)
    with pytest.raises(AdmissionError, match='freshness'):
        ResourceAdmissionGate(adapter=adapter, clock=clock, freshness_seconds=0)
    with pytest.raises(AdmissionError, match='measure'):
        ResourceAdmissionGate(adapter=object(), clock=clock, freshness_seconds=10)


def test_host_adapter_reports_honest_unknowns(clock):
    adapter = HostResourceAdapter(clock=clock, ram_reader=lambda: None)
    m = adapter.measure()
    assert m.ram_mb is None       # honestly unmeasured on this host
    assert m.vram_mb is None      # never guessed
    assert m.measured_at == 1000.0
    gate = ResourceAdmissionGate(adapter=adapter, clock=clock, freshness_seconds=30)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=1, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'ram_mb' in decision.reason


def test_allowed_decision_names_local_only_scope(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=8000))
    assert 'LOCAL' in decision.reason

import pytest

from controller.resource_admission import (
    AdmissionError,
    AdmissionRequest,
    HostResourceAdapter,
    ResourceAdmissionGate,
    _effective_cpu_capacity_cores,
    _parse_cgroup_v2_cpu_max,
    _read_cgroup_v2_cpu_quota_cores,
    ResourceMeasurements,
)

VERDICT_ALLOWED = 'ALLOWED_LOCAL'
VERDICT_DENIED = 'DENIED_LOCAL'


class FakeAdapter:
    def __init__(self, clock, values):
        self._clock = clock
        # Own copy: tests mutate _values (e.g. inject a stale measured_at);
        # that must never leak into the shared module-level GOOD dict.
        self._values = dict(values)

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
    assert 'cpu_cores 16.0 > local_cap 8.0' in decision.reason


def test_insufficient_ram_is_denied(clock):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=4, ram_mb=32000))
    assert decision.verdict == VERDICT_DENIED
    assert 'ram_mb 32000 > local_cap 16000' in decision.reason


def test_quota_caps_capacity_and_allows_work_below_cap(clock):
    gate = make_gate(clock, GOOD, quota={'cpu_cores': 4, 'ram_mb': 8000})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=2, ram_mb=4000))
    assert decision.verdict == VERDICT_ALLOWED


def test_request_above_local_quota_is_denied(clock):
    gate = make_gate(clock, GOOD, quota={'cpu_cores': 4, 'ram_mb': 8000})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=5, ram_mb=4000))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores 5.0 > local_cap 4' in decision.reason


def test_measured_capacity_remains_upper_bound_when_quota_is_higher(clock):
    gate = make_gate(clock, GOOD, quota={'cpu_cores': 16, 'ram_mb': 32000})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=9, ram_mb=4000))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores 9.0 > local_cap 8.0' in decision.reason


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


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_cpu_request_is_denied(clock, bad_value):
    gate = make_gate(clock, GOOD)
    decision = gate.request_admission(AdmissionRequest(cpu_cores=bad_value, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores' in decision.reason


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_measured_cpu_is_denied(clock, bad_value):
    gate = make_gate(clock, {**GOOD, 'cpu_cores': bad_value})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=1, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'cpu_cores' in decision.reason


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_measurement_timestamp_is_denied(clock, bad_value):
    gate = make_gate(clock, {**GOOD, 'measured_at': bad_value})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=1, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'timestamp' in decision.reason


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_freshness_window_is_rejected(clock, bad_value):
    adapter = FakeAdapter(clock, GOOD)
    with pytest.raises(AdmissionError, match='finite and positive'):
        ResourceAdmissionGate(adapter=adapter, clock=clock, freshness_seconds=bad_value)


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_quota_limit_is_rejected(clock, bad_value):
    adapter = FakeAdapter(clock, GOOD)
    with pytest.raises(AdmissionError, match='finite and non-negative'):
        ResourceAdmissionGate(
            adapter=adapter, clock=clock, freshness_seconds=30,
            quota={'cpu_cores': bad_value},
        )


def test_future_measurement_timestamp_is_denied(clock):
    gate = make_gate(clock, {**GOOD, 'measured_at': 1001.0})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=1, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'future' in decision.reason


@pytest.mark.parametrize('bad_value', [float('nan'), float('inf'), float('-inf')])
def test_non_finite_optional_vram_measurement_is_denied(clock, bad_value):
    gate = make_gate(clock, {**GOOD, 'vram_mb': bad_value})
    decision = gate.request_admission(AdmissionRequest(cpu_cores=1, ram_mb=100))
    assert decision.verdict == VERDICT_DENIED
    assert 'vram_mb' in decision.reason



def test_cgroup_v2_cpu_quota_is_parsed_as_cores(tmp_path):
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text("150000 100000", encoding="utf-8")
    assert _read_cgroup_v2_cpu_quota_cores(path=str(cpu_max)) == 1.5


def test_cgroup_v2_max_means_no_quota(tmp_path):
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text("max 100000", encoding="utf-8")
    assert _read_cgroup_v2_cpu_quota_cores(path=str(cpu_max)) is None


@pytest.mark.parametrize("content", ["", "broken", "100000 0", "-1 100000", "x 100000"])
def test_malformed_cgroup_cpu_quota_is_rejected(tmp_path, content):
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        _read_cgroup_v2_cpu_quota_cores(path=str(cpu_max))


def test_effective_cpu_capacity_uses_the_lower_affinity_or_quota():
    assert _effective_cpu_capacity_cores(8, 2.5) == 2.5
    assert _effective_cpu_capacity_cores(2, 8.0) == 2.0


def test_effective_cpu_capacity_fails_closed_on_unknown_or_zero():
    assert _effective_cpu_capacity_cores(None, None) is None
    assert _effective_cpu_capacity_cores(8, 0.0) is None


def test_host_adapter_uses_injected_effective_cpu_capacity(clock):
    adapter = HostResourceAdapter(
        clock=clock,
        ram_reader=lambda: 4096,
        cpu_capacity_reader=lambda: 1.5,
    )
    assert adapter.measure().cpu_cores == 1.5



def test_cgroup_v2_uses_tightest_quota_across_ancestors(tmp_path):
    cgroup_file = tmp_path / "proc-cgroup"
    cgroup_file.write_text("0::/tenant.slice/container.scope", encoding="utf-8")
    mount = tmp_path / "cgroup"
    leaf = mount / "tenant.slice" / "container.scope"
    parent = mount / "tenant.slice"
    leaf.mkdir(parents=True)
    parent.mkdir(parents=True, exist_ok=True)
    (leaf / "cpu.max").write_text("300000 100000", encoding="utf-8")
    (parent / "cpu.max").write_text("200000 100000", encoding="utf-8")
    (mount / "cpu.max").write_text("max 100000", encoding="utf-8")
    assert _read_cgroup_v2_cpu_quota_cores(
        cgroup_file=str(cgroup_file), mount_root=str(mount)
    ) == 2.0


def test_cgroup_v2_parser_rejects_malformed_content():
    with pytest.raises(ValueError):
        _parse_cgroup_v2_cpu_max("bad quota")



def test_cgroup_v1_cpu_controller_is_not_mistaken_for_unlimited(tmp_path):
    cgroup_file = tmp_path / "proc-cgroup"
    cgroup_file.write_text("2:cpu,cpuacct:/tenant.slice", encoding="utf-8")
    with pytest.raises(ValueError, match="cgroup v1 CPU quota is unsupported"):
        _read_cgroup_v2_cpu_quota_cores(
            cgroup_file=str(cgroup_file), mount_root=str(tmp_path / "cgroup")
        )

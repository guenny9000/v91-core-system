"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Local resource measurement and deterministic, bounded admission.

Issue #47, stage 3. Core rule: missing or stale measurements mean
UNKNOWN / NO_CAPACITY - never unlimited capacity. A request is only
admitted when every required resource is actually measured, fresh, and
sufficient, and within the locally configured quota.

What is real here:
- HostResourceAdapter measures what the standard library can honestly
  measure LOCALLY: effective process CPU capacity (affinity plus Linux
  cgroup v2 CPU quota when present), free disk space (shutil.disk_usage),
  and RAM available from /proc/meminfo on Linux. On platforms without
  process-affinity APIs, system logical CPUs are the available topology
  fallback, not idle CPU. On non-Linux platforms RAM stays None (UNKNOWN),
  and VRAM is never guessed (None).
- ResourceAdmissionGate is deterministic: injected clock, explicit
  freshness window, explicit quota, fail-closed on every gap.
- DETECTION != AUTHORIZATION: an ALLOWED_LOCAL admission is permission
  to start local work only - no global or remote authority at all.

Honest limits:
- No load sampling, no trend prediction: a single measurement is a
  snapshot, not a capacity forecast. CPU affinity/cgroup quota describes
  the process's schedulable ceiling, not currently idle CPU.
"""
from __future__ import annotations

import math
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

VERDICT_ALLOWED = "ALLOWED_LOCAL"
VERDICT_DENIED = "DENIED_LOCAL"


def _is_finite_number(value: Any) -> bool:
    """Accept finite int/float values, but never bool, NaN, or infinity."""
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and (not isinstance(value, float) or math.isfinite(value))
    )


@dataclass(frozen=True)
class ResourceMeasurements:
    cpu_cores: Optional[float]
    ram_mb: Optional[int]
    vram_mb: Optional[int]
    disk_mb: Optional[int]
    measured_at: float

    def missing_fields(self) -> list[str]:
        missing = []
        if not _is_finite_number(self.cpu_cores) or self.cpu_cores <= 0:
            missing.append("cpu_cores")
        for name, value in (("ram_mb", self.ram_mb), ("disk_mb", self.disk_mb)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                missing.append(name)
        if self.vram_mb is not None and (
            isinstance(self.vram_mb, bool)
            or not isinstance(self.vram_mb, int)
            or self.vram_mb <= 0
        ):
            missing.append("vram_mb")
        return missing


@dataclass(frozen=True)
class AdmissionRequest:
    cpu_cores: float
    ram_mb: int
    disk_mb: int = 0
    vram_mb: Optional[int] = None  # None = VRAM not required by this request

    def invalid_fields(self) -> list[str]:
        bad = []
        if not _is_finite_number(self.cpu_cores) or self.cpu_cores <= 0:
            bad.append("cpu_cores")
        if isinstance(self.ram_mb, bool) or not isinstance(self.ram_mb, int) or self.ram_mb <= 0:
            bad.append("ram_mb")
        if isinstance(self.disk_mb, bool) or not isinstance(self.disk_mb, int) or self.disk_mb < 0:
            bad.append("disk_mb")
        if self.vram_mb is not None and (
            isinstance(self.vram_mb, bool)
            or not isinstance(self.vram_mb, int)
            or self.vram_mb <= 0
        ):
            bad.append("vram_mb")
        return bad


@dataclass(frozen=True)
class AdmissionDecision:
    verdict: str
    reason: str
    measurements: Optional[ResourceMeasurements] = None

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "reason": self.reason}


class AdmissionError(ValueError):
    """Raised when the admission contract is violated."""


def _linux_ram_available_mb() -> Optional[int]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    kib = int(line.split()[1])
                    return kib // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _parse_cgroup_v2_cpu_max(content: str) -> Optional[float]:
    """Parse one cgroup v2 cpu.max value; None means that level has no quota."""
    fields = content.strip().split()
    if len(fields) != 2:
        raise ValueError("Malformed cgroup v2 cpu.max")
    quota_text, period_text = fields
    if quota_text == "max":
        return None
    try:
        quota = int(quota_text)
        period = int(period_text)
    except ValueError as exc:
        raise ValueError("Malformed cgroup v2 cpu.max") from exc
    if quota < 0 or period <= 0:
        raise ValueError("Invalid cgroup v2 CPU quota or period")
    return quota / period


def _read_cgroup_v2_cpu_quota_cores(
    path: Optional[str] = None,
    cgroup_file: str = "/proc/self/cgroup",
    mount_root: str = "/sys/fs/cgroup",
) -> Optional[float]:
    """Read the tightest cgroup v2 quota from the process cgroup to its root."""
    if path is not None:
        paths = [path]
    else:
        try:
            with open(cgroup_file, "r", encoding="utf-8") as handle:
                entries = handle.read().splitlines()
        except FileNotFoundError:
            return None
        relative_path = None
        has_v1_cpu_controller = False
        for entry in entries:
            fields = entry.split(":", 2)
            if len(fields) != 3:
                continue
            if fields[0] == "0" and fields[1] == "":
                relative_path = fields[2].strip("/")
                break
            if "cpu" in fields[1].split(","):
                has_v1_cpu_controller = True
        if relative_path is None:
            if has_v1_cpu_controller:
                raise ValueError("cgroup v1 CPU quota is unsupported; CPU capacity is UNKNOWN")
            return None  # no cgroup v2 or v1 CPU controller is exposed
        components = [part for part in relative_path.split("/") if part]
        paths = [
            os.path.join(mount_root, *components[:depth], "cpu.max")
            for depth in range(len(components), -1, -1)
        ]

    quotas = []
    for candidate in paths:
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                quota = _parse_cgroup_v2_cpu_max(handle.read())
        except FileNotFoundError:
            continue
        if quota is not None:
            quotas.append(quota)
    return min(quotas) if quotas else None


def _effective_cpu_capacity_cores(
    affinity_count: Optional[int], quota_cores: Optional[float],
) -> Optional[float]:
    """Bound process CPU capacity by affinity and any cgroup v2 quota."""
    if isinstance(affinity_count, bool) or not isinstance(affinity_count, int) or affinity_count <= 0:
        return None
    capacity = float(affinity_count)
    if quota_cores is not None:
        if not _is_finite_number(quota_cores) or quota_cores <= 0:
            return None
        capacity = min(capacity, float(quota_cores))
    return capacity


def _available_cpu_capacity_cores() -> Optional[float]:
    """Return process schedulable CPU ceiling, never a claim about idle CPU."""
    try:
        if hasattr(os, "sched_getaffinity"):
            affinity_count = len(os.sched_getaffinity(0))
        else:
            affinity_count = os.cpu_count()
        quota_cores = _read_cgroup_v2_cpu_quota_cores()
        return _effective_cpu_capacity_cores(affinity_count, quota_cores)
    except (OSError, ValueError, TypeError):
        # A present but unreadable/malformed limit must not inflate capacity.
        return None


class HostResourceAdapter:
    """Measures locally available resources with stdlib means, honestly bounded."""

    def __init__(self, clock: Optional[Callable[[], float]] = None,
                 ram_reader: Callable[[], Optional[int]] = _linux_ram_available_mb,
                 cpu_capacity_reader: Callable[[], Optional[float]] = _available_cpu_capacity_cores) -> None:
        self._clock = clock if clock is not None else time.monotonic
        self._ram_reader = ram_reader
        self._cpu_capacity_reader = cpu_capacity_reader

    def measure(self) -> ResourceMeasurements:
        cores = self._cpu_capacity_reader()
        disk = None
        try:
            disk = shutil.disk_usage(os.getcwd()).free // (1024 * 1024)
        except OSError:
            disk = None
        ram = self._ram_reader()
        return ResourceMeasurements(
            cpu_cores=float(cores) if cores else None,
            ram_mb=ram,
            vram_mb=None,  # never guessed; a GPU adapter must report itself
            disk_mb=disk,
            measured_at=self._clock(),
        )


class ResourceAdmissionGate:
    """Deterministic, bounded, local-only admission over fresh measurements."""

    def __init__(self, *, adapter: Any, clock: Callable[[], float],
                 freshness_seconds: float,
                 quota: Optional[dict[str, float]] = None) -> None:
        if not callable(clock):
            raise AdmissionError("clock must be callable")
        if not _is_finite_number(freshness_seconds) or freshness_seconds <= 0:
            raise AdmissionError("freshness_seconds must be finite and positive")
        if adapter is None or not callable(getattr(adapter, "measure", None)):
            raise AdmissionError("adapter must provide a callable measure()")
        allowed_quota_keys = {"cpu_cores", "ram_mb", "disk_mb", "vram_mb"}
        if quota is not None and not isinstance(quota, dict):
            raise AdmissionError("quota must be a mapping of finite resource limits")
        normalized_quota = dict(quota) if quota is not None else {}
        for key, limit in normalized_quota.items():
            if key not in allowed_quota_keys:
                raise AdmissionError(f"unsupported quota resource: {key}")
            if not _is_finite_number(limit) or limit < 0:
                raise AdmissionError(f"quota for {key} must be finite and non-negative")
        self._adapter = adapter
        self._clock = clock
        self._freshness = float(freshness_seconds)
        self._quota = normalized_quota

    def _effective_capacity(self, key: str, measured: float) -> float:
        """Apply a local ceiling to measured capacity; never reject a host merely
        because its measured capacity is greater than the owner's quota.
        """
        limit = self._quota.get(key)
        return min(measured, limit) if limit is not None else measured

    def request_admission(self, request: AdmissionRequest) -> AdmissionDecision:
        """Admit local work only if all requirements are measured, fresh and sufficient."""
        invalid = request.invalid_fields()
        if invalid:
            return AdmissionDecision(VERDICT_DENIED,
                                     f"Malformed request, invalid fields: {invalid}.")
        measurements = self._adapter.measure()
        if not isinstance(measurements, ResourceMeasurements):
            return AdmissionDecision(VERDICT_DENIED, "Adapter returned no valid measurements.")
        missing = measurements.missing_fields()
        if missing:
            return AdmissionDecision(
                VERDICT_DENIED,
                f"UNKNOWN is never unlimited: unmeasured or invalid resource(s) {missing} -> NO_CAPACITY.",
                measurements)
        if not _is_finite_number(measurements.measured_at):
            return AdmissionDecision(
                VERDICT_DENIED, "Measurement timestamp is missing or non-finite.", measurements)
        now = self._clock()
        if not _is_finite_number(now):
            return AdmissionDecision(
                VERDICT_DENIED, "Admission clock returned a non-finite timestamp.", measurements)
        age = now - measurements.measured_at
        if age < 0:
            return AdmissionDecision(
                VERDICT_DENIED, "Measurement timestamp is in the future; refusing admission.", measurements)
        if age > self._freshness:
            return AdmissionDecision(
                VERDICT_DENIED,
                f"Stale measurement (age {age:.1f}s > {self._freshness:.1f}s).",
                measurements)
        # A quota is a ceiling on what this gate may allocate, not a condition
        # that the host's total measured capacity must itself satisfy.
        capacities = {
            "cpu_cores": self._effective_capacity("cpu_cores", measurements.cpu_cores),
            "ram_mb": self._effective_capacity("ram_mb", measurements.ram_mb),
            "disk_mb": self._effective_capacity("disk_mb", measurements.disk_mb),
        }
        if measurements.vram_mb is not None:
            capacities["vram_mb"] = self._effective_capacity(
                "vram_mb", measurements.vram_mb)
        deficits = []
        if request.cpu_cores > capacities["cpu_cores"]:
            deficits.append(f"cpu_cores {float(request.cpu_cores)} > local_cap {capacities['cpu_cores']}")
        if request.ram_mb > capacities["ram_mb"]:
            deficits.append(f"ram_mb {request.ram_mb} > local_cap {capacities['ram_mb']}")
        if request.disk_mb > capacities["disk_mb"]:
            deficits.append(f"disk_mb {request.disk_mb} > local_cap {capacities['disk_mb']}")
        if request.vram_mb is not None:
            if measurements.vram_mb is None:
                return AdmissionDecision(
                    VERDICT_DENIED,
                    "VRAM required but never measured on this host (UNKNOWN is never unlimited).",
                    measurements)
            if request.vram_mb > capacities["vram_mb"]:
                deficits.append(f"vram_mb {request.vram_mb} > local_cap {capacities['vram_mb']}")
        if deficits:
            return AdmissionDecision(VERDICT_DENIED,
                                     f"Insufficient resources: {'; '.join(deficits)}.",
                                     measurements)
        return AdmissionDecision(
            VERDICT_ALLOWED,
            "All requirements measured, fresh, sufficient and within local quota; "
            "admission is permission for LOCAL work only.",
            measurements)

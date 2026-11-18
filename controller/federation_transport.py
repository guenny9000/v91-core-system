#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Federation transport binding (Issue #103, Phase 2).

Wires a FederationReceiver to a UDP socket and NOTHING else:
- loopback-only by default (127.0.0.1 / ::1); any other bind host must
  be passed via an explicit allowlist and is still refused by default
  (Zero Trust: a listener is a liability, SHIPPING != INSTALLATION)
- every datagram is handed to the receiver as exact raw bytes; the
  receiver alone decides ACCEPTED/REJECTED (DETECTION != AUTHORIZATION)
- rejected or oversized datagrams are never re-parsed, never executed,
  and never answered (no reflected traffic)
- bounded, in-memory outcome log for observability; it is not durable
  and not a ledger (the receiver's quarantine ledger is)

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO peer discovery, NO dial-out, NO mesh routing: one socket, one
  receiver callback
- UDP is intentionally unauthenticated at the socket layer; all trust
  lives in Ed25519 envelope signatures and replay floors
- NO systemd unit, NO daemonization, NO /opt deployment in this phase;
  running this in production requires a separately reviewed host config
"""
from __future__ import annotations

import socket
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable

from controller.federation_receiver import FederationReceiver, Receipt

DEFAULT_ALLOWED_BIND_HOSTS = frozenset({"127.0.0.1", "::1"})
MAX_DATAGRAM_BYTES = 65536  # OS cap; the receiver enforces MAX_ENVELOPE_BYTES


class TransportError(Exception):
    """Fail-closed transport error (constructor or bind problems)."""


@dataclass(frozen=True)
class TransportOutcome:
    peer_addr: tuple
    size: int
    status: str
    reason: str


class UdpEnvelopeListener:
    """Loopback UDP listener that hands raw datagrams to a receiver."""

    def __init__(self, *, receiver: FederationReceiver, port: int = 0,
                 host: str = "127.0.0.1",
                 allowed_bind_hosts: frozenset[str] = DEFAULT_ALLOWED_BIND_HOSTS,
                 outcome_log_size: int = 128) -> None:
        if not isinstance(receiver, FederationReceiver):
            raise TransportError("an authenticated FederationReceiver is required (fail-closed)")
        if type(port) is not int or port < 0 or port > 65535:
            raise TransportError("port must be an int in [0, 65535]")
        if host not in allowed_bind_hosts:
            raise TransportError(
                f"bind host {host!r} is not in the allowlist {sorted(allowed_bind_hosts)}; "
                "refusing to open a non-allowlisted listener (Zero Trust)")
        if type(outcome_log_size) is not int or outcome_log_size < 1:
            raise TransportError("outcome_log_size must be a positive int")
        self._receiver = receiver
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._outcomes: deque[TransportOutcome] = deque(maxlen=outcome_log_size)
        self._counts = {"accepted": 0, "rejected": 0}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def bound_address(self) -> tuple:
        if self._sock is None:
            raise TransportError("listener not started")
        return self._sock.getsockname()

    def outcomes(self) -> list[TransportOutcome]:
        with self._lock:
            return list(self._outcomes)

    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def start(self) -> "UdpEnvelopeListener":
        if self._running:
            raise TransportError("listener already running")
        family = socket.AF_INET6 if ":" in self._host else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_DGRAM)
        try:
            sock.bind((self._host, self._port))
        except OSError as exc:
            sock.close()
            raise TransportError(f"bind to {self._host}:{self._port} failed: {exc}") from exc
        sock.settimeout(0.5)  # poll loop so stop() is honored promptly
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._serve, name="v91-fed-udp",
                                        daemon=True)
        self._thread.start()
        return self

    def _serve(self) -> None:
        sock = self._sock
        while self._running and sock is not None:
            try:
                raw, addr = sock.recvfrom(MAX_DATAGRAM_BYTES)
            except socket.timeout:
                continue
            except OSError:
                break  # socket closed during stop()
            receipt: Receipt = self._receiver.receive(raw)
            outcome = TransportOutcome(peer_addr=addr, size=len(raw),
                                       status=receipt.status, reason=receipt.reason)
            with self._lock:
                self._outcomes.append(outcome)
                key = "accepted" if receipt.status == "ACCEPTED" else "rejected"
                self._counts[key] += 1

    def stop(self) -> None:
        self._running = False
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> "UdpEnvelopeListener":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


# Deliberately NOT provided here: a run-forever daemon loop, systemd
# integration, or outbound federation (sending envelopes). Sending is
# a separate capability with its own review; receiving is the risky
# surface and stays minimal, loopback, and allowlisted.

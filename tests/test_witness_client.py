import asyncio

import pytest

from controller.state_monotonicity import V91StateMonotonicityGuard
from controller.witness_client import V91WitnessMockNetworkClient


class LocalState:
    def get_database_id(self):
        return "db-test"

    def get_last_logged_sequence(self):
        return 7

    def compute_current_state_hash(self):
        return "a" * 64


def test_mock_witness_response_verifies_with_guard():
    async def scenario():
        witness = V91WitnessMockNetworkClient()
        challenge = await witness.async_request_challenge("https://mock.invalid")
        heartbeat = await witness.async_submit_state_for_signing(
            database_id="db-test", epoch=1, sequence_id=7,
            state_hash="a" * 64, challenge=challenge,
        )
        guard = V91StateMonotonicityGuard(
            LocalState(), {witness.key_id: witness.public_key}
        )
        valid, reason = guard.verify_state_integrity(
            heartbeat, expected_challenge=challenge, key_id=witness.key_id
        )
        assert valid is True
        assert reason == "STATE_VALID_AND_MONOTONIC"

    asyncio.run(scenario())


def test_mock_challenge_is_single_use():
    async def scenario():
        witness = V91WitnessMockNetworkClient()
        challenge = await witness.async_request_challenge("grpc://mock.invalid")
        args = dict(
            database_id="db-test", epoch=1, sequence_id=7,
            state_hash="a" * 64, challenge=challenge,
        )
        await witness.async_submit_state_for_signing(**args)
        with pytest.raises(ValueError):
            await witness.async_submit_state_for_signing(**args)

    asyncio.run(scenario())


def test_mock_does_not_accept_unknown_challenge():
    async def scenario():
        witness = V91WitnessMockNetworkClient()
        with pytest.raises(ValueError):
            await witness.async_submit_state_for_signing(
                database_id="db-test", epoch=1, sequence_id=7,
                state_hash="a" * 64, challenge="b" * 64,
            )

    asyncio.run(scenario())

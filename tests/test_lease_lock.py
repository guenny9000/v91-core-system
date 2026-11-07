import pytest

from controller.lease_lock import Lease, LeaseLockError, LeaseLockManager


@pytest.fixture
def clock():
    state = {'now': 100.0}
    return lambda: state['now']


@pytest.fixture
def manager(clock):
    return LeaseLockManager(clock=clock)


def test_acquire_returns_lease_with_first_token(manager):
    lease = manager.acquire('task-a', 'node-1', 10)
    assert isinstance(lease, Lease)
    assert lease.fencing_token == 1
    assert lease.holder_id == 'node-1'
    assert lease.expires_at == 110.0


def test_second_acquire_is_refused_while_held(manager):
    assert manager.acquire('task-a', 'node-1', 10) is not None
    assert manager.acquire('task-a', 'node-2', 10) is None


def test_same_holder_cannot_double_acquire(manager):
    manager.acquire('task-a', 'node-1', 10)
    assert manager.acquire('task-a', 'node-1', 10) is None


def test_expired_lock_is_free_again(clock, manager):
    manager.acquire('task-a', 'node-1', 10)
    clock()['now'] = 111.0  # lease expired at 110
    lease = manager.acquire('task-a', 'node-2', 10)
    assert lease is not None
    assert lease.holder_id == 'node-2'


def test_fencing_token_strictly_increases_across_expiry(clock, manager):
    first = manager.acquire('task-a', 'node-1', 10)
    clock()['now'] = 111.0
    second = manager.acquire('task-a', 'node-2', 10)
    assert first.fencing_token == 1
    assert second.fencing_token == 2


def test_stale_holder_is_fenced_after_takeover(clock, manager):
    old = manager.acquire('task-a', 'node-1', 10)
    clock()['now'] = 111.0
    manager.acquire('task-a', 'node-2', 10)
    # node-1 wakes up late with its old token:
    assert manager.is_fenced('task-a', old.fencing_token) is True
    assert manager.validate_action('task-a', 'node-1', old.fencing_token) is False
    assert manager.validate_action('task-a', 'node-2', 2) is True


def test_current_holder_is_not_fenced(manager):
    lease = manager.acquire('task-a', 'node-1', 10)
    assert manager.is_fenced('task-a', lease.fencing_token) is False


def test_renew_extends_live_lease(clock, manager):
    manager.acquire('task-a', 'node-1', 10)
    renewed = manager.renew('task-a', 'node-1', 1, 10)
    assert renewed.expires_at == 120.0


def test_renew_of_expired_lease_is_refused(clock, manager):
    manager.acquire('task-a', 'node-1', 10)
    clock()['now'] = 111.0
    with pytest.raises(LeaseLockError, match='expired'):
        manager.renew('task-a', 'node-1', 1, 10)


def test_renew_by_wrong_holder_is_refused(manager):
    manager.acquire('task-a', 'node-1', 10)
    with pytest.raises(LeaseLockError, match='current lease holder'):
        manager.renew('task-a', 'node-2', 1, 10)


def test_release_requires_matching_holder_and_token(manager):
    manager.acquire('task-a', 'node-1', 10)
    with pytest.raises(LeaseLockError, match='matching fencing token'):
        manager.release('task-a', 'node-1', 999)
    with pytest.raises(LeaseLockError, match='matching fencing token'):
        manager.release('task-a', 'node-2', 1)
    manager.release('task-a', 'node-1', 1)
    assert manager.current('task-a') is None
    # released: lock is free, token still fenced for late writers:
    assert manager.is_fenced('task-a', 1) is True


def test_validate_action_after_expiry_is_false(clock, manager):
    manager.acquire('task-a', 'node-1', 10)
    clock()['now'] = 111.0
    assert manager.validate_action('task-a', 'node-1', 1) is False


def test_invalid_arguments_are_rejected(manager):
    with pytest.raises(LeaseLockError, match='lock_id'):
        manager.acquire('', 'node-1', 10)
    with pytest.raises(LeaseLockError, match='duration'):
        manager.acquire('task-a', 'node-1', 0)


def test_independent_locks_have_independent_tokens(manager):
    a = manager.acquire('task-a', 'node-1', 10)
    b = manager.acquire('task-b', 'node-1', 10)
    assert a.fencing_token == 1
    assert b.fencing_token == 1
    assert manager.is_fenced('task-a', b.fencing_token) is False

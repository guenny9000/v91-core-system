import pytest

from controller.model_runner import PinnedModelRunner
from controller.replay_session import (
    COMBINED_BYTE_MATCH,
    INDEPENDENCE_CLAIM,
    ReplaySessionError,
    TwoNodeReplay,
)

MODEL = 'a' * 64
TOKENIZER = 'b' * 64
RUNTIME = 'c' * 64


def make_runner(inference=lambda b: b'echo:' + b, **overrides):
    values = {
        'inference': inference,
        'model_digest': MODEL,
        'tokenizer_digest': TOKENIZER,
        'runtime_digest': RUNTIME,
        'seed': 7,
        'parameters': {'temperature': 0},
        'precision': 'fp16',
        'backend': 'cpu-reference',
    }
    values.update(overrides)
    return PinnedModelRunner(**values)


def test_same_instance_is_refused():
    r = make_runner()
    with pytest.raises(ReplaySessionError, match='different runner instances'):
        TwoNodeReplay(reference_runner=r, replay_runner=r)


def test_non_runner_arguments_are_refused():
    with pytest.raises(ReplaySessionError, match='PinnedModelRunner'):
        TwoNodeReplay(reference_runner=make_runner(), replay_runner='nope')


def test_exact_match_of_two_instances():
    session = TwoNodeReplay(reference_runner=make_runner(),
                            replay_runner=make_runner())
    result = session.execute(b'prompt')
    assert result['status'] == 'VERIFIED_EXACT'
    assert result['combined_status'] == COMBINED_BYTE_MATCH


def test_non_bytes_input_is_refused():
    session = TwoNodeReplay(reference_runner=make_runner(), replay_runner=make_runner())
    with pytest.raises(ReplaySessionError, match='bytes'):
        session.execute('prompt')


def test_diverging_outputs_are_nondeterministic():
    session = TwoNodeReplay(reference_runner=make_runner(),
                            replay_runner=make_runner(inference=lambda b: b'other'))
    result = session.execute(b'prompt')
    assert result['status'] == 'NONDETERMINISTIC'
    assert result['combined_status'] == 'NONDETERMINISTIC'


def test_different_seed_is_conditions_mismatch():
    session = TwoNodeReplay(reference_runner=make_runner(seed=7),
                            replay_runner=make_runner(seed=8))
    result = session.execute(b'prompt')
    assert result['status'] == 'CONDITIONS_MISMATCH'


def test_shared_callable_is_disclosed_honestly():
    shared = lambda b: b'out'  # noqa: E731
    session = TwoNodeReplay(reference_runner=make_runner(inference=shared),
                            replay_runner=make_runner(inference=shared))
    result = session.execute(b'prompt')
    assert result['shared_inference_callable'] is True
    assert result['status'] == 'VERIFIED_EXACT'


def test_distinct_callables_are_disclosed():
    session = TwoNodeReplay(reference_runner=make_runner(),
                            replay_runner=make_runner(inference=lambda b: b'echo:' + b))
    result = session.execute(b'prompt')
    assert result['shared_inference_callable'] is False


def test_node_independence_is_never_claimed():
    session = TwoNodeReplay(reference_runner=make_runner(), replay_runner=make_runner())
    result = session.execute(b'prompt')
    assert result['node_independence'] == INDEPENDENCE_CLAIM


def test_both_manifests_are_completed_unverified():
    session = TwoNodeReplay(reference_runner=make_runner(), replay_runner=make_runner())
    result = session.execute(b'prompt')
    assert result['reference']['status'] == 'COMPLETED_UNVERIFIED'
    assert result['replay']['status'] == 'COMPLETED_UNVERIFIED'


def test_runs_are_recorded_by_their_own_runners():
    a = make_runner()
    b = make_runner()
    session = TwoNodeReplay(reference_runner=a, replay_runner=b)
    session.execute(b'prompt')
    # a produced the reference, b the replay - a must refuse to verify both:
    ref = a.run(b'prompt')
    assert a.verify_independent_replay(ref, ref)['status'] == 'SELF_VERIFICATION_REFUSED'


def test_sessions_are_independent_objects():
    a1, b1 = make_runner(), make_runner()
    a2, b2 = make_runner(), make_runner(inference=lambda b: b'other')
    s1 = TwoNodeReplay(reference_runner=a1, replay_runner=b1)
    s2 = TwoNodeReplay(reference_runner=a2, replay_runner=b2)
    assert s1.execute(b'prompt')['status'] == 'VERIFIED_EXACT'
    assert s2.execute(b'prompt')['status'] == 'NONDETERMINISTIC'

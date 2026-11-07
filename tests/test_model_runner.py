import pytest

from controller.model_runner import ModelRunnerError, PinnedModelRunner

MODEL = 'a' * 64
TOKENIZER = 'b' * 64
RUNTIME = 'c' * 64


def runner(inference=lambda b: b'echo:' + b, **overrides):
    values = {
        'inference': inference,
        'model_digest': MODEL,
        'tokenizer_digest': TOKENIZER,
        'runtime_digest': RUNTIME,
        'seed': 7,
        'parameters': {'temperature': 0, 'top_p': 1},
        'precision': 'fp16',
        'backend': 'cpu-reference',
    }
    values.update(overrides)
    return PinnedModelRunner(**values)


def test_run_produces_completed_unverified_record():
    manifest = runner().run(b'prompt')
    assert manifest['status'] == 'COMPLETED_UNVERIFIED'
    assert len(manifest['input_digest']) == 64
    assert manifest['output_digest'] != manifest['input_digest']


def test_inference_callable_is_required():
    with pytest.raises(ModelRunnerError, match='callable'):
        runner(inference='not-callable')


def test_invalid_model_digest_is_rejected():
    with pytest.raises(ModelRunnerError, match='model_digest'):
        runner(model_digest='short')


def test_negative_seed_is_rejected():
    with pytest.raises(ModelRunnerError, match='seed'):
        runner(seed=-1)


def test_non_bytes_input_is_rejected():
    with pytest.raises(ModelRunnerError, match='bytes'):
        runner().run('prompt')


def test_non_bytes_output_is_rejected():
    with pytest.raises(ModelRunnerError, match='bytes'):
        runner(inference=lambda b: 'text').run(b'prompt')


def test_sampled_temperature_is_refused_by_default():
    with pytest.raises(ModelRunnerError, match='allow_nondeterministic'):
        runner(parameters={'temperature': 0.7})


def test_do_sample_is_refused_by_default():
    with pytest.raises(ModelRunnerError, match='allow_nondeterministic'):
        runner(parameters={'do_sample': True})


def test_explicit_nondeterministic_run_is_recorded_honestly():
    manifest = runner(parameters={'temperature': 0.7}, allow_nondeterministic=True).run(b'prompt')
    assert manifest['status'] == 'COMPLETED_UNVERIFIED'


def test_self_verification_of_two_own_runs_is_refused():
    r = runner()
    first = r.run(b'prompt')
    second = r.run(b'prompt')
    result = r.verify_independent_replay(first, second)
    assert result['status'] == 'SELF_VERIFICATION_REFUSED'


def test_own_record_against_independent_replay_is_allowed():
    r = runner()
    own = r.run(b'prompt')
    external = runner().run(b'prompt')
    result = r.verify_independent_replay(own, external)
    assert result['status'] == 'VERIFIED_EXACT'


def test_diverging_independent_replay_is_nondeterministic():
    own = runner().run(b'prompt')
    diverging = runner(inference=lambda b: b'other').run(b'prompt')
    result = runner().verify_independent_replay(own, diverging)
    assert result['status'] == 'NONDETERMINISTIC'


def test_produced_here_rejects_non_manifests():
    with pytest.raises(ModelRunnerError, match='not a run manifest'):
        runner().produced_here({'input_digest': 'x'})

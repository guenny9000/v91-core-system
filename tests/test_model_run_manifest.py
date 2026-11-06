import pytest

from controller.model_run_manifest import (
    ModelRunManifestError,
    build_run_manifest,
    verify_exact_replay,
)


MODEL = 'a' * 64
TOKENIZER = 'b' * 64
RUNTIME = 'c' * 64


def run(output=b'answer', **overrides):
    values = {
        'model_digest': MODEL,
        'tokenizer_digest': TOKENIZER,
        'runtime_digest': RUNTIME,
        'input_bytes': b'prompt',
        'output_bytes': output,
        'seed': 42,
        'parameters': {'temperature': 0, 'top_p': 1},
        'precision': 'fp16',
        'backend': 'cpu-reference',
    }
    values.update(overrides)
    return build_run_manifest(**values)


def test_identical_pinned_replay_is_exact():
    assert verify_exact_replay(run(), run())['status'] == 'VERIFIED_EXACT'


def test_different_output_with_same_conditions_is_nondeterministic():
    result = verify_exact_replay(run(b'first'), run(b'second'))
    assert result['status'] == 'NONDETERMINISTIC'


def test_changed_seed_is_conditions_mismatch():
    result = verify_exact_replay(run(), run(seed=43))
    assert result['status'] == 'CONDITIONS_MISMATCH'


def test_changed_model_artifact_is_conditions_mismatch():
    result = verify_exact_replay(run(), run(model_digest='d' * 64))
    assert result['status'] == 'CONDITIONS_MISMATCH'


def test_settings_tampering_is_rejected():
    manifest = run()
    manifest['settings']['temperature'] = 0.7
    with pytest.raises(ModelRunManifestError, match='settings digest mismatch'):
        verify_exact_replay(manifest, run())


def test_invalid_digest_is_rejected():
    with pytest.raises(ModelRunManifestError):
        run(model_digest='not-a-digest')


def test_boolean_seed_is_rejected():
    with pytest.raises(ModelRunManifestError, match='seed'):
        run(seed=True)


def test_non_finite_settings_are_rejected():
    with pytest.raises(ModelRunManifestError, match='finite JSON'):
        run(parameters={'temperature': float('nan')})


def test_non_bytes_input_is_rejected():
    with pytest.raises(ModelRunManifestError, match='bytes'):
        run(input_bytes='prompt')
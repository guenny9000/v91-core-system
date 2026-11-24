import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
CLI_ENV = {**os.environ, 'PYTHONPATH': REPO_ROOT}

import pytest

from controller.independent_replay_gate import (
    GATE_VERSION,
    IndependentReplayError,
    verify_independent_replay,
)
from controller.model_run_manifest import (
    ModelRunManifestError,
    build_run_manifest,
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


def test_independent_identical_replay_is_verified():
    verdict = verify_independent_replay(
        run(), run(), producer_id='node-producer', verifier_id='node-verifier')
    assert verdict['status'] == 'VERIFIED_EXACT_INDEPENDENT'
    assert verdict['gate_version'] == GATE_VERSION
    assert verdict['producer_id'] == 'node-producer'
    assert verdict['verifier_id'] == 'node-verifier'


def test_self_verification_is_forbidden():
    with pytest.raises(IndependentReplayError, match='SELF_VERIFICATION_FORBIDDEN'):
        verify_independent_replay(run(), run(),
                                  producer_id='node-a', verifier_id='node-a')


def test_missing_producer_id_is_rejected():
    with pytest.raises(IndependentReplayError, match='producer_id'):
        verify_independent_replay(run(), run(),
                                  producer_id='', verifier_id='node-b')


def test_untrimmed_verifier_id_is_rejected():
    with pytest.raises(IndependentReplayError, match='trimmed'):
        verify_independent_replay(run(), run(),
                                  producer_id='node-a', verifier_id=' node-b')


def test_overlong_verifier_id_is_rejected():
    with pytest.raises(IndependentReplayError, match='128'):
        verify_independent_replay(run(), run(),
                                  producer_id='node-a', verifier_id='x' * 129)


def test_conditions_mismatch_never_verifies():
    verdict = verify_independent_replay(run(), run(seed=43),
                                        producer_id='node-a',
                                        verifier_id='node-b')
    assert verdict['status'] == 'CONDITIONS_MISMATCH'


def test_nondeterministic_replay_never_verifies():
    verdict = verify_independent_replay(run(b'first'), run(b'second'),
                                        producer_id='node-a',
                                        verifier_id='node-b')
    assert verdict['status'] == 'NONDETERMINISTIC'


def test_malformed_reference_propagates():
    broken = run()
    broken['settings']['temperature'] = 0.7
    with pytest.raises(ModelRunManifestError):
        verify_independent_replay(broken, run(),
                                  producer_id='node-a', verifier_id='node-b')


def test_cli_independent_exact_replay_exits_zero(tmp_path):
    reference = tmp_path / 'reference.json'
    replay = tmp_path / 'replay.json'
    reference.write_text(json.dumps(run()), encoding='utf-8')
    replay.write_text(json.dumps(run()), encoding='utf-8')
    proc = subprocess.run(
        [sys.executable, '-m', 'controller.independent_replay_gate',
         '--reference', str(reference), '--replay', str(replay),
         '--producer-id', 'node-a', '--verifier-id', 'node-b'],
        capture_output=True, text=True, cwd=str(tmp_path), env=CLI_ENV)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['status'] == 'VERIFIED_EXACT_INDEPENDENT'


def test_cli_self_verification_exits_two(tmp_path):
    reference = tmp_path / 'reference.json'
    reference.write_text(json.dumps(run()), encoding='utf-8')
    proc = subprocess.run(
        [sys.executable, '-m', 'controller.independent_replay_gate',
         '--reference', str(reference), '--replay', str(reference),
         '--producer-id', 'node-a', '--verifier-id', 'node-a'],
        capture_output=True, text=True, cwd=str(tmp_path), env=CLI_ENV)
    assert proc.returncode == 2
    assert 'SELF_VERIFICATION_FORBIDDEN' in proc.stderr


def test_cli_conditions_mismatch_exits_one(tmp_path):
    reference = tmp_path / 'reference.json'
    replay = tmp_path / 'replay.json'
    reference.write_text(json.dumps(run()), encoding='utf-8')
    replay.write_text(json.dumps(run(seed=43)), encoding='utf-8')
    proc = subprocess.run(
        [sys.executable, '-m', 'controller.independent_replay_gate',
         '--reference', str(reference), '--replay', str(replay),
         '--producer-id', 'node-a', '--verifier-id', 'node-b'],
        capture_output=True, text=True, cwd=str(tmp_path), env=CLI_ENV)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)['status'] == 'CONDITIONS_MISMATCH'


def test_cli_missing_file_exits_two(tmp_path):
    proc = subprocess.run(
        [sys.executable, '-m', 'controller.independent_replay_gate',
         '--reference', str(tmp_path / 'absent.json'),
         '--replay', str(tmp_path / 'absent.json'),
         '--producer-id', 'node-a', '--verifier-id', 'node-b'],
        capture_output=True, text=True, cwd=str(tmp_path), env=CLI_ENV)
    assert proc.returncode == 2
    assert 'I/O error' in proc.stderr

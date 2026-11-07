from pathlib import Path

import controller


def test_controller_import_resolves_to_repository_package():
    expected = Path(__file__).resolve().parents[1] / "controller"
    assert Path(controller.__file__).resolve().parent == expected

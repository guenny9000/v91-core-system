"""Stabilize package imports before legacy tests add controller/ to sys.path."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Load the repository package before legacy tests add controller/ itself to
# sys.path. Otherwise controller/controller.py can shadow the package name.
import controller  # noqa: F401,E402

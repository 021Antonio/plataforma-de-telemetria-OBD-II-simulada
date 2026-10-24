"""Suíte de conformidade do dialeto ELM327 contra qualquer servidor TCP."""

import sys
from pathlib import Path

_TESTS = str(Path(__file__).resolve().parents[1])
if _TESTS not in sys.path:  # `python -m tests.conformance` fora do pytest (que já põe tests/)
    sys.path.insert(0, _TESTS)

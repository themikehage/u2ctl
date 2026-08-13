"""Pytest configuration and shared fixtures for unit and contract testing."""

import sys
import io
import pytest
from typing import List, Dict, Any, Tuple

from u2ctl.cli import main


@pytest.fixture
def invoke_cli():
    """In-process CLI execution fixture capturing stdout, stderr, and exit code."""
    def _run(args: List[str]) -> Tuple[int, str, str]:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            sys.stdout = stdout_buf
            sys.stderr = stderr_buf
            code = main(args)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()
    return _run

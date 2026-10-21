"""orglens.el's ERT suite, run batch and bare (`-Q`) with the rest.

Skipped when no Emacs is found: `emacs` on PATH, else `ORGLENS_EMACS`, else
the macOS application. `-Q` loads no init file and no packages, so nothing
of a person's Emacs is read; the tests use a fixture cache of their own.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MAC = "/Applications/Emacs.app/Contents/MacOS/Emacs"


def _emacs() -> str | None:
    for candidate in (shutil.which("emacs"), os.environ.get("ORGLENS_EMACS"), MAC):
        if candidate and Path(candidate).exists():
            return candidate
    return None


@pytest.mark.skipif(_emacs() is None, reason="no Emacs on this machine")
def test_orglens_el():
    env = {k: v for k, v in os.environ.items() if k != "ORGLENS_CONFIG"}
    result = subprocess.run(
        [_emacs(), "-Q", "--batch", "-L", "emacs", "-l", "tests/emacs/orglens-test.el",
         "-f", "ert-run-tests-batch-and-exit"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert " 0 unexpected" in result.stdout + result.stderr


@pytest.mark.skipif(_emacs() is None, reason="no Emacs on this machine")
def test_orglens_el_compiles_without_warnings(tmp_path):
    target = tmp_path / "orglens.el"
    shutil.copy(REPO / "emacs" / "orglens.el", target)
    result = subprocess.run(
        [_emacs(), "-Q", "--batch", "--eval",
         f'(progn (setq byte-compile-error-on-warn t) '
         f'(unless (byte-compile-file "{target}") (kill-emacs 1)))'],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr

"""Loading a WORKFLOW.yaml definition."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_workflow(path: Path) -> dict:
    """Read a WORKFLOW.yaml. Raises FileNotFoundError if absent — never guesses."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no workflow definition at {path}")
    return yaml.safe_load(path.read_text()) or {}

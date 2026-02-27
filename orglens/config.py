"""Config loading and management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from orglens.grammar import Grammar


@dataclass
class Config:
    docs_root: Path
    grammar_name: str
    _config_dir: Path | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """Load config from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        if "docs_root" not in data:
            raise ValueError("docs_root is required in config")

        docs_root = Path(data["docs_root"]).expanduser()
        grammar_name = data.get("grammar", "default")

        return cls(
            docs_root=docs_root,
            grammar_name=grammar_name,
            _config_dir=path.parent,
        )

    @classmethod
    def load(cls) -> Config:
        """Load config from the default location."""
        config_path = Path("~/.config/orglens/config.yaml").expanduser()
        if not config_path.exists():
            raise FileNotFoundError(
                f"No config found at {config_path}. "
                "Create it with:\n\n"
                "  mkdir -p ~/.config/orglens\n"
                "  echo 'docs_root: ~/path/to/your/docs' > ~/.config/orglens/config.yaml\n"
            )
        return cls.from_yaml(config_path)

    def load_grammar(self) -> Grammar:
        """Load the grammar specified in config."""
        if self.grammar_name == "default":
            grammar_path = Path(__file__).parent / "grammars" / "default.yaml"
        else:
            grammar_path = Path(self.grammar_name).expanduser()
        return Grammar.from_yaml(grammar_path)

    @property
    def snapshot_path(self) -> Path:
        """Path where the topology snapshot is written."""
        config_dir = self._config_dir or Path("~/.config/orglens").expanduser()
        cache_dir = config_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "snapshot.md"

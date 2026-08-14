"""Config loading and management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from orglens.grammar import Grammar


@dataclass
class Config:
    roots: list[Path]
    grammar_name: str
    docs_base_url: str = "http://localhost:8000"
    _config_dir: Path | None = None

    @property
    def docs_root(self) -> Path:
        """The first root. Kept while callers are migrated to `roots`."""
        return self.roots[0]

    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """Load config from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # `docs_root` is the one-tree spelling of `roots`. Both are accepted:
        # a config written before units still names one tree, and that tree is
        # simply the first root.
        declared = data.get("roots") or (
            [data["docs_root"]] if data.get("docs_root") else None
        )
        if not declared:
            raise ValueError("roots is required in config (or docs_root, for one tree)")

        return cls(
            roots=[Path(r).expanduser() for r in declared],
            grammar_name=data.get("grammar", "default"),
            # Where the tree is served. `mkdocs serve` by default; set it to a
            # published site and the same links work from anywhere.
            docs_base_url=(data.get("docs_base_url") or "http://localhost:8000").rstrip("/"),
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

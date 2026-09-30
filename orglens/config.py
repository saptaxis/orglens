"""Config loading, and the one directory orglens keeps on a machine.

`~/.orglens/` holds the config, the snapshot cache, and the event log. The
config and the cache can be rebuilt; the event log cannot, which is why
`bootstrap --uninstall` never touches this directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from orglens import skip as skip_rule
from orglens.grammar import Grammar

ORGLENS_HOME = Path.home() / ".orglens"


def _skip(data: dict) -> tuple[str, ...]:
    """`skip:` as given, or the default when absent. A bare string is refused
    rather than iterated: `skip: node_modules` would otherwise skip every
    folder whose name is one letter."""
    if "skip" not in data:
        return skip_rule.DEFAULT
    value = data["skip"]
    if value is None:
        value = []
    if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
        raise ValueError("skip must be a list of folder names (globs allowed)")
    return tuple(value)


@dataclass
class Config:
    roots: list[Path]
    grammar_name: str
    docs_base_url: str = "http://localhost:8000"
    #: What a view link opens: `served` (the doc at `docs_base_url`) or
    #: `file` (the file itself, for a tree read in an editor).
    view_link: str = "served"
    #: Folder names no walk enters (`skip.py`). The whole list: a config's
    #: `skip:` replaces the default rather than adding to it.
    skip: tuple[str, ...] = skip_rule.DEFAULT
    _config_dir: Path | None = None

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
            view_link=data.get("view_link", "served"),
            skip=_skip(data),
            _config_dir=path.parent,
        )

    @classmethod
    def current(cls) -> Config:
        """The config in force: `ORGLENS_CONFIG` when set, else the default
        location. What the CLI loads, for readers outside the CLI."""
        import os
        path = os.environ.get("ORGLENS_CONFIG")
        config = cls.from_yaml(Path(path).expanduser()) if path else cls.load()
        skip_rule.use(config.skip)
        return config

    @classmethod
    def load(cls) -> Config:
        """Load config from the default location."""
        config_path = ORGLENS_HOME / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"No config found at {config_path}. "
                "Create it with:\n\n"
                f"  mkdir -p {ORGLENS_HOME}\n"
                f"  echo 'roots: [~/path/to/your/docs]' > {config_path}\n"
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
        config_dir = self._config_dir or ORGLENS_HOME
        cache_dir = config_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "snapshot.md"

    @property
    def snapshot_json_path(self) -> Path:
        """The snapshot as data, for programs: completion reads this rather
        than parsing headings out of the markdown one."""
        return self.snapshot_path.with_suffix(".json")

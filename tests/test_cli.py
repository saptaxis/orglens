"""The commands, and what they refuse to know on their own."""

import pytest
from click.testing import CliRunner

from orglens.cli import cli
from orglens.declaration import MARKER


@pytest.fixture
def runner():
    return CliRunner()


def _roots_config(tmp_path, roots, grammar_path=None) -> dict:
    """A config file naming these roots, as an env dict for `runner.invoke`."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / f"config-{len(list(config_dir.iterdir()))}.yaml"
    lines = ["roots:"] + [f"  - {r}" for r in roots]
    if grammar_path:
        lines.append(f"grammar: {grammar_path}")
    config_file.write_text("\n".join(lines) + "\n")
    return {"ORGLENS_CONFIG": str(config_file)}


def _declare(path, unit: str, kind: str, part_of: str | None = None) -> None:
    """Write a marker that declares `path` as its own unit, home named after it."""
    path.mkdir(parents=True, exist_ok=True)
    lines = [f"home: {unit}", f"unit: {unit}", f"kind: {kind}"]
    if part_of:
        lines.append(f"part_of: {part_of}")
    lines.append(f"homes:\n  - {unit}")
    (path / MARKER).write_text("\n".join(lines) + "\n")


@pytest.fixture
def units_tree(tmp_path):
    """A one-root tree of declared units, one per real kind in the default grammar."""
    docs = tmp_path / "docs"

    clipcompose = docs / "projects" / "clipcompose"
    _declare(clipcompose, "clipcompose", "project")
    (clipcompose / "specs").mkdir()
    (clipcompose / "plans").mkdir()
    (clipcompose / "overview.md").write_text("# Overview\n\n> **Status:** Active\n")
    (clipcompose / "plans" / "01-packaging-Feb252026.md").write_text("# 01 — Packaging\n")
    (clipcompose / "specs" / "agent-integration.md").write_text("# Agent Integration\n")

    orglens = docs / "projects" / "orglens"
    _declare(orglens, "orglens", "project")
    (orglens / "overview.md").write_text("# Overview\n\n> **Status:** Design complete\n")

    physics = docs / "research" / "physics-priors"
    _declare(physics, "physics-priors", "research-program")
    (physics / "overview.md").write_text("# Overview\n\n> **Status:** Design complete\n")

    expt = physics / "expt-1-agent-behavior"
    _declare(expt, "expt-1-agent-behavior", "experiment", part_of="physics-priors")
    (expt / "plans").mkdir()
    (expt / "overview.md").write_text("# Overview\n\n> **Status:** Running\n")
    (expt / "plans" / "01-testbed-Feb032026.md").write_text("# 01 — Testbed\n")

    freightify = docs / "clients" / "freightify"
    _declare(freightify, "freightify", "client")
    (freightify / "overview.md").write_text("# Overview\n\n> **Status:** Active\n")

    return docs


@pytest.fixture
def cli_env(tmp_path, units_tree):
    """Config env for the units tree."""
    return _roots_config(tmp_path, [units_tree])


@pytest.fixture
def deck_env(tmp_path, units_tree):
    """A grammar with a kind the engine has never heard of, and one declared unit of it."""
    grammar = tmp_path / "deck.yaml"
    grammar.write_text(
        "version: 2\n"
        "driver: DECK.md\n"
        "entities:\n"
        "  deck: capabilities/*\n"
        "artifacts:\n"
        "  card:\n"
        "    find: cards/*.md\n"
        "    means: One instruction to one model.\n"
    )
    writing = units_tree / "capabilities" / "writing"
    _declare(writing, "writing", "deck")
    (writing / "cards").mkdir()
    (writing / "cards" / "voice.md").write_text("# Voice\n")

    return _roots_config(tmp_path, [units_tree], grammar_path=grammar)


class TestListCommand:
    def test_list_all(self, runner, cli_env):
        result = runner.invoke(cli, ["list"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" in result.output

    def test_list_by_kind(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "project"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" not in result.output

    def test_a_nested_unit_shows_what_it_is_part_of(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "experiment"], env=cli_env)
        assert result.exit_code == 0
        assert "[physics-priors]" in result.output

    def test_an_unknown_kind_says_what_the_kinds_are(self, runner, cli_env):
        """This raised `KeyError: 'deck'` — the CLI never asked the grammar."""
        result = runner.invoke(cli, ["list", "--type", "deck"], env=cli_env)

        assert result.exit_code == 1
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert "Unknown kind: deck" in result.output
        assert "project" in result.output


class TestAKindTheEngineHasNeverHeardOf:
    def test_listing_it_needs_no_python_change(self, runner, deck_env):
        """`deck` is a unit's declared kind, not one the grammar names."""
        result = runner.invoke(cli, ["list", "--type", "deck"], env=deck_env)

        assert result.exit_code == 0
        assert "writing" in result.output

    def test_finding_its_documents_needs_no_python_change(self, runner, deck_env):
        result = runner.invoke(cli, ["find", "card"], env=deck_env)

        assert result.exit_code == 0
        assert "voice.md" in result.output

    def test_creating_one_needs_no_python_change(self, runner, deck_env, units_tree):
        target = units_tree / "capabilities" / "interior"
        result = runner.invoke(cli, ["new", str(target), "--kind", "deck"], env=deck_env)

        assert result.exit_code == 0
        assert target.is_dir()
        assert (target / MARKER).exists()


class TestStatusCommand:
    def test_status_shows_units(self, runner, cli_env):
        result = runner.invoke(cli, ["status"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "Active" in result.output

    def test_the_authored_line_is_quoted_whole(self, runner, cli_env, units_tree):
        """It is a sentence someone wrote, not a field to be trimmed."""
        overview = units_tree / "projects" / "clipcompose" / "overview.md"
        overview.write_text(
            "# Overview\n\n"
            "> **Status:** Plans 01-04 complete; v2 plan on branch v2-plan1\n"
        )

        result = runner.invoke(cli, ["status"], env=cli_env)

        assert result.exit_code == 0
        assert "Plans 01-04 complete; v2 plan on branch v2-plan1" in result.output

    def test_the_line_is_shown_with_its_age(self, runner, cli_env):
        """Three real status lines are five months behind their trees."""
        result = runner.invoke(cli, ["status"], env=cli_env)

        assert result.exit_code == 0
        assert "old]" in result.output

    def test_the_author_s_case_survives(self, runner, cli_env):
        result = runner.invoke(cli, ["status"], env=cli_env)
        assert result.exit_code == 0
        assert "Active" in result.output


class TestFindCommand:
    def test_find_across_the_tree(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "plan"], env=cli_env)
        assert result.exit_code == 0
        assert "01-packaging-Feb252026.md" in result.output

    def test_find_scoped_to_a_part_finds_its_own_documents(self, runner, cli_env):
        """A part is its own unit now — scoping to it, not to its parent,
        is what reaches its documents."""
        result = runner.invoke(cli, ["find", "plan", "expt-1-agent-behavior"], env=cli_env)
        assert result.exit_code == 0
        assert "01-testbed-Feb032026.md" in result.output

    def test_find_scoped_to_the_parent_does_not_reach_its_parts(self, runner, cli_env):
        """A unit's documents are its own homes' documents — a part's
        documents belong to the part, not to whatever it is declared part of."""
        result = runner.invoke(cli, ["find", "plan", "physics-priors"], env=cli_env)
        assert "01-testbed-Feb032026.md" not in result.output

    def test_find_specs(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "spec", "clipcompose"], env=cli_env)
        assert result.exit_code == 0
        assert "agent-integration.md" in result.output

    def test_a_document_with_no_recognisable_name_is_still_found(
        self, runner, cli_env, units_tree
    ):
        (units_tree / "projects" / "clipcompose" / "plans" / "02-stg-setup.md").write_text("x")

        result = runner.invoke(cli, ["find", "plan", "clipcompose"], env=cli_env)

        assert "02-stg-setup.md" in result.output

    def test_an_unknown_document_kind_says_what_the_kinds_are(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "memo"], env=cli_env)

        assert result.exit_code == 1
        assert "Unknown document kind: memo" in result.output


class TestNewCommand:
    def test_new_unit(self, runner, cli_env, units_tree):
        target = units_tree / "projects" / "test-tool"
        result = runner.invoke(cli, ["new", str(target), "--kind", "project"], env=cli_env)

        assert result.exit_code == 0
        assert (target / MARKER).exists()
        assert target.is_dir()

    def test_the_declaration_names_the_unit_and_kind(self, runner, cli_env, units_tree):
        target = units_tree / "projects" / "test-tool"
        runner.invoke(cli, ["new", str(target), "--kind", "project"], env=cli_env)

        result = runner.invoke(cli, ["where", "test-tool"], env=cli_env)
        assert "unit:   test-tool  (project)" in result.output

    def test_part_of_is_recorded(self, runner, cli_env, units_tree):
        target = units_tree / "research" / "physics-priors" / "expt-2-world-model"
        result = runner.invoke(
            cli,
            ["new", str(target), "--kind", "experiment", "--part-of", "physics-priors"],
            env=cli_env,
        )

        assert result.exit_code == 0
        where = runner.invoke(cli, ["where", "expt-2-world-model"], env=cli_env)
        assert "in:     physics-priors" in where.output

    def test_position_places_nothing(self, runner, cli_env, tmp_path):
        """The path given is exactly where the directory lands — no pattern
        decides that any more, so anywhere at all is a legal place to create."""
        target = tmp_path / "somewhere-else" / "my-thing"
        result = runner.invoke(cli, ["new", str(target), "--kind", "project"], env=cli_env)

        assert result.exit_code == 0
        assert target.is_dir()

    def test_creating_over_an_existing_directory_is_refused(self, runner, cli_env, units_tree):
        result = runner.invoke(
            cli, ["new", str(units_tree / "projects" / "clipcompose"), "--kind", "project"],
            env=cli_env,
        )

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_creating_under_a_root_is_quiet(self, runner, cli_env, units_tree):
        """No enumeration blind spot here — no note needed."""
        target = units_tree / "projects" / "test-tool"
        result = runner.invoke(cli, ["new", str(target), "--kind", "project"], env=cli_env)

        assert result.exit_code == 0
        assert "note:" not in result.output

    def test_creating_outside_every_root_warns_but_still_creates(self, runner, cli_env, tmp_path):
        """`list`, `status`, `snapshot` and `check` only sweep the configured
        roots — a unit created outside all of them would otherwise be a
        silent blind spot, reachable only by `where` while standing inside
        it. Warn, don't refuse: the model allows this, un-met until a root
        is added or someone works in it."""
        target = tmp_path / "elsewhere" / "my-thing"
        result = runner.invoke(cli, ["new", str(target), "--kind", "project"], env=cli_env)

        assert result.exit_code == 0
        assert target.is_dir()
        assert (target / MARKER).exists()
        assert "note:" in result.output
        assert "none of your configured roots" in result.output

    def test_a_root_reached_through_a_symlink_is_still_recognised(
        self, runner, tmp_path, units_tree
    ):
        """Resolved before compared: `~/Dropbox` is a symlink to
        `~/Library/CloudStorage/Dropbox` here, and an unresolved comparison
        would warn about a unit that is, in fact, right where it should be."""
        link = tmp_path / "via-symlink"
        link.symlink_to(units_tree)
        env = _roots_config(tmp_path, [link])

        target = link / "projects" / "test-tool"
        result = runner.invoke(cli, ["new", str(target), "--kind", "project"], env=env)

        assert result.exit_code == 0
        assert "note:" not in result.output


class TestWhereCommand:
    def test_it_names_the_roots_and_where_the_config_came_from(self, runner, cli_env, units_tree):
        result = runner.invoke(cli, ["where"], env=cli_env)

        assert result.exit_code == 0
        assert str(units_tree) in result.output
        assert "config:" in result.output

    def test_a_named_unit_gives_an_absolute_path(self, runner, cli_env, units_tree):
        """The path is the point — a relative one cannot be acted on safely."""
        result = runner.invoke(cli, ["where", "clipcompose"], env=cli_env)

        assert result.exit_code == 0
        assert "unit:   clipcompose  (project)" in result.output
        assert str(units_tree / "projects" / "clipcompose") in result.output

    def test_it_says_how_each_home_resolved(self, runner, cli_env):
        """`clipcompose` declares its own home via marker — the strongest rung."""
        result = runner.invoke(cli, ["where", "clipcompose"], env=cli_env)

        assert "(marker)" in result.output

    def test_a_part_names_what_it_belongs_to(self, runner, cli_env):
        result = runner.invoke(cli, ["where", "expt-1-agent-behavior"], env=cli_env)

        assert "in:     physics-priors" in result.output

    def test_standing_inside_a_unit_needs_no_argument(
        self, runner, cli_env, units_tree, monkeypatch
    ):
        monkeypatch.chdir(units_tree / "projects" / "clipcompose" / "specs")

        result = runner.invoke(cli, ["where"], env=cli_env)

        assert "unit:   clipcompose  (project)" in result.output
        assert "here:   projects/clipcompose/specs" in result.output

    def test_standing_outside_the_roots_says_so_rather_than_guessing(
        self, runner, cli_env, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["where"], env=cli_env)

        assert result.exit_code == 0
        assert "outside the roots" in result.output
        assert "unit:   none" in result.output

    def test_an_unknown_name_fails_rather_than_resolving_to_nothing(self, runner, cli_env):
        result = runner.invoke(cli, ["where", "nonexistent"], env=cli_env)

        assert result.exit_code == 1

    def test_a_home_across_two_roots(self, runner, tmp_path, grammar):
        """The reason units exist: a code checkout and a docs checkout, one unit."""
        docs = tmp_path / "traitful-docs" / "docs"
        code = tmp_path / "code"
        unit_docs = docs / "projects" / "orglens"
        unit_docs.mkdir(parents=True)
        (unit_docs / MARKER).write_text(
            "home: traitful-docs/docs/projects/orglens\n"
            "unit: orglens\nkind: project\n"
            "homes:\n  - orglens\n  - traitful-docs/docs/projects/orglens\n"
        )
        (code / "orglens").mkdir(parents=True)
        (code / "traitful-docs" / "docs" / "projects" / "orglens").mkdir(parents=True)

        result = runner.invoke(
            cli, ["where", "orglens"], env=_roots_config(tmp_path, [docs, code])
        )

        assert "unit:   orglens  (project)" in result.output
        assert "orglens" in result.output
        assert "(name)" in result.output
        assert "(marker)" in result.output


class TestCheckCommand:
    def test_a_clean_tree_reports_nothing(self, runner, tmp_path):
        docs = tmp_path / "docs"
        proj = docs / "projects" / "clipcompose"
        _declare(proj, "clipcompose", "project")
        (proj / "overview.md").write_text("# Overview\n")
        # One of each artifact kind, so the default grammar's plan/log/spec
        # globs have somewhere to match — without this the tree is drift-free
        # but still reports those kinds as unmatched anywhere.
        (proj / "plans").mkdir()
        (proj / "plans" / "01-x-Feb252026.md").write_text("# 01\n")
        (proj / "logs").mkdir()
        (proj / "logs" / "01-x-Feb252026-log.md").write_text("# Log\n")
        (proj / "specs").mkdir()
        (proj / "specs" / "x.md").write_text("# Spec\n")

        result = runner.invoke(cli, ["check"], env=_roots_config(tmp_path, [docs]))

        assert result.exit_code == 0
        assert "No drift" in result.output

    def test_drift_is_reported_and_nothing_is_hidden(self, runner, tmp_path):
        docs = tmp_path / "docs"
        proj = docs / "projects" / "clipcompose"
        _declare(proj, "clipcompose", "project")  # no overview.md written
        env = _roots_config(tmp_path, [docs])

        check = runner.invoke(cli, ["check"], env=env)
        listing = runner.invoke(cli, ["list"], env=env)

        assert check.exit_code == 0
        assert "clipcompose" in check.output
        assert "overview.md" in check.output
        assert "clipcompose" in listing.output  # reported, never gated

    def test_a_near_miss_is_named(self, runner, tmp_path):
        docs = tmp_path / "docs"
        near = docs / "research" / "llm-probing"
        _declare(near, "llm-probing", "research-program")
        (near / "question.md").write_text("# Question\n")

        result = runner.invoke(cli, ["check"], env=_roots_config(tmp_path, [docs]))

        assert "likely the same thing" in result.output
        assert "question.md" in result.output

    def test_undeclared_work_is_reported_never_gated(self, runner, tmp_path):
        """A directory that never declared itself is the migration worklist,
        not a silent gap: `check` names it, and `list` does not see it at all
        — it is not a unit, only a candidate."""
        docs = tmp_path / "docs"
        (docs / "projects" / "resume").mkdir(parents=True)  # no marker
        env = _roots_config(tmp_path, [docs])

        check = runner.invoke(cli, ["check"], env=env)

        assert check.exit_code == 0
        assert "undeclared: " in check.output
        assert "resume" in check.output

    def test_a_home_resolved_by_name_only_is_reported_as_weak(self, runner, tmp_path):
        docs = tmp_path / "traitful-docs" / "docs"
        code = tmp_path / "code"
        unit_docs = docs / "projects" / "orglens"
        unit_docs.mkdir(parents=True)
        (unit_docs / MARKER).write_text(
            "home: traitful-docs/docs/projects/orglens\n"
            "unit: orglens\nkind: project\n"
            "homes:\n  - orglens\n  - traitful-docs/docs/projects/orglens\n"
        )
        (unit_docs / "overview.md").write_text("# Overview\n")
        (code / "orglens").mkdir(parents=True)
        (code / "traitful-docs" / "docs" / "projects" / "orglens").mkdir(parents=True)

        result = runner.invoke(cli, ["check"], env=_roots_config(tmp_path, [docs, code]))

        assert "orglens: home 'orglens' resolved by directory name only" in result.output


class TestSnapshotCommand:
    def test_snapshot_writes_file(self, runner, cli_env):
        result = runner.invoke(cli, ["snapshot"], env=cli_env)
        assert result.exit_code == 0
        assert "Snapshot written" in result.output

    def test_snapshot_to_stdout(self, runner, cli_env):
        result = runner.invoke(cli, ["snapshot", "--stdout"], env=cli_env)
        assert result.exit_code == 0
        assert "Topology Snapshot" in result.output


class TestAgainstTheSharedTwoRootFixture:
    """The fixture other modules already use for the marker-spans-two-roots
    case, pointed at through the CLI rather than the `Registry` directly."""

    def test_where_names_the_unit_and_how_each_home_resolved(
        self, runner, two_root_tree, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path / "code" / "orglens")
        env = _roots_config(tmp_path, two_root_tree.roots)

        result = runner.invoke(cli, ["where"], env=env)

        assert "orglens" in result.output
        assert "(name)" in result.output

    def test_list_groups_by_declared_kind(self, runner, two_root_tree, tmp_path):
        env = _roots_config(tmp_path, two_root_tree.roots)

        result = runner.invoke(cli, ["list"], env=env)

        assert "orglens" in result.output

    def test_check_prints_undeclared_candidates(self, runner, two_root_tree, tmp_path):
        env = _roots_config(tmp_path, two_root_tree.roots)

        result = runner.invoke(cli, ["check"], env=env)

        assert "reelmill" in result.output


class TestViewCommand:
    def test_a_document_under_the_second_root_gets_a_served_link(self, runner, tmp_path):
        """`view` used to build its URL context from `config.docs_root` — the
        first root only — so a document living under the second root
        silently fell back to a `file://` link instead of a served one."""
        root_a = tmp_path / "docs"
        root_b = tmp_path / "code"
        home = root_a / "projects" / "sample"
        home.mkdir(parents=True)
        (home / MARKER).write_text(
            "home: sample\nunit: sample\nkind: project\n"
            "homes:\n  - sample\n  - sample-code\n"
        )
        (home / "overview.md").write_text("# Overview\n")
        second_home = root_b / "sample-code"
        second_home.mkdir(parents=True)
        (second_home / "notes.md").write_text("# Notes\n")

        out = tmp_path / "view.html"
        env = _roots_config(tmp_path, [root_a, root_b])
        result = runner.invoke(
            cli,
            ["view", "--out", str(out), "--no-open", "--base-url", "http://localhost:9999"],
            env=env,
        )

        assert result.exit_code == 0
        page = out.read_text()
        assert "notes.md" in page
        assert "http://localhost:9999" in page
        assert "file://" not in page


class TestReferenceCommand:
    def test_it_renders_the_grammar(self, runner, cli_env):
        result = runner.invoke(cli, ["reference"], env=cli_env)

        assert result.exit_code == 0
        assert "research-program" in result.output
        assert "do not edit" in result.output

    def test_it_can_be_written_out(self, runner, cli_env, tmp_path):
        out = tmp_path / "generated" / "grammar-reference.md"

        result = runner.invoke(cli, ["reference", "--out", str(out)], env=cli_env)

        assert result.exit_code == 0
        assert out.read_text().startswith("<!-- generated")

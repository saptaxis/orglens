"""The commands, and what they refuse to know on their own."""

import os
import subprocess
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from orglens.activity import Activity
from orglens.cli import _grouped, cli
from orglens.declaration import MARKER
from orglens.homes import Home
from orglens.units import Unit


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


def _unit(name: str, kind: str) -> Unit:
    """A unit with one home, named after itself — enough for `_grouped`,
    which only ever looks at `.kind` and uses the unit itself as a key."""
    home = Home(name=name, path=Path(f"/{name}"), how="marker")
    return Unit(name=name, kind=kind, homes=(home,), part_of=None, declared_at=Path(f"/{name}"))


class TestGroupedOrdering:
    """`_grouped` is what makes `list` and `status` recent-first: units
    within a kind ordered by `activity.recency`, and the kinds themselves
    led by whichever holds the newest member. Built from plain `Activity`
    objects — no git, no scad, no filesystem — because the ordering itself
    doesn't care where the dates came from.
    """

    def test_the_latest_clock_wins_not_the_same_clock_for_every_unit(self):
        """Unit `a` was edited recently but hasn't had a session in ages;
        unit `b` is the reverse. Neither clock alone would put them in the
        right order — only taking the latest of the two does."""
        a = _unit("a", "project")
        b = _unit("b", "project")
        acts = {
            a: Activity(modified=1_000_000_000, last_session=100),
            b: Activity(modified=100, last_session=2_000_000_000),
        }

        groups = _grouped([a, b], acts)

        [(_, members)] = groups
        assert [u.name for u in members] == ["b", "a"]

    def test_groups_are_led_by_their_newest_member(self):
        project = _unit("proj", "project")
        client = _unit("client", "client")
        acts = {
            project: Activity(modified=100),
            client: Activity(modified=2_000_000_000),
        }

        groups = _grouped([project, client], acts)

        assert [kind for kind, _ in groups] == ["client", "project"]

    def test_a_unit_with_no_activity_still_appears_last_without_raising(self):
        a = _unit("a", "project")
        b = _unit("b", "project")  # never keyed into acts at all
        acts = {a: Activity(modified=500)}

        groups = _grouped([a, b], acts)

        [(_, members)] = groups
        assert [u.name for u in members] == ["a", "b"]


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

    def test_its_dates_are_labelled_by_clock(self, runner, cli_env):
        """A bare '26d ago' never says whether that is a commit, an edit, or
        a session — the fixture's units are never committed, only edited, so
        the labelled clock that shows up must say 'edited'."""
        result = runner.invoke(cli, ["status"], env=cli_env)

        assert result.exit_code == 0
        assert "edited" in result.output


def _age(path: Path) -> None:
    """Push every file under `path` back 30 days, marker included — so a
    unit that should read as stale actually does, regardless of which file
    inside it `_newest_mtime` happens to find newest."""
    old = time.time() - 86400 * 30
    for f in path.rglob("*"):
        if f.is_file():
            os.utime(f, (old, old))


class TestRecentFirstOrdering:
    """`list` and `status` used to sort alphabetically, which answers the
    wrong question. These exercise the real commands end to end — sorting
    by file mtime alone, since a scad session index is not under test here.
    """

    def test_list_orders_units_within_a_kind_by_recency(self, runner, tmp_path):
        docs = tmp_path / "docs"
        alpha = docs / "projects" / "alpha"
        zeta = docs / "projects" / "zeta"
        _declare(alpha, "alpha", "project")
        _declare(zeta, "zeta", "project")
        (alpha / "overview.md").write_text("# Overview\n")
        (zeta / "overview.md").write_text("# Overview\n")
        _age(alpha)  # zeta stays at "now" — edited more recently than alpha

        result = runner.invoke(cli, ["list"], env=_roots_config(tmp_path, [docs]))

        assert result.exit_code == 0
        # "zeta" sorts after "alpha" alphabetically but was edited later.
        assert result.output.index("zeta") < result.output.index("alpha")

    def test_list_shows_when_a_unit_was_last_edited(self, runner, tmp_path):
        docs = tmp_path / "docs"
        unit = docs / "projects" / "solo"
        _declare(unit, "solo", "project")
        (unit / "overview.md").write_text("# Overview\n")

        result = runner.invoke(cli, ["list"], env=_roots_config(tmp_path, [docs]))

        assert result.exit_code == 0
        assert "edited" in result.output

    def test_list_orders_groups_by_their_newest_member(self, runner, tmp_path):
        docs = tmp_path / "docs"
        proj = docs / "projects" / "proj"
        client = docs / "clients" / "client"
        _declare(proj, "proj", "project")
        _declare(client, "client", "client")
        (proj / "overview.md").write_text("# Overview\n")
        (client / "overview.md").write_text("# Overview\n")
        _age(proj)  # client stays at "now" — its group should lead

        result = runner.invoke(cli, ["list"], env=_roots_config(tmp_path, [docs]))

        assert result.exit_code == 0
        assert result.output.index("Clients:") < result.output.index("Projects:")

    def test_status_also_orders_by_recency(self, runner, tmp_path):
        docs = tmp_path / "docs"
        alpha = docs / "projects" / "alpha"
        zeta = docs / "projects" / "zeta"
        _declare(alpha, "alpha", "project")
        _declare(zeta, "zeta", "project")
        (alpha / "overview.md").write_text("# Overview\n")
        (zeta / "overview.md").write_text("# Overview\n")
        _age(alpha)

        result = runner.invoke(cli, ["status"], env=_roots_config(tmp_path, [docs]))

        assert result.exit_code == 0
        assert result.output.index("zeta") < result.output.index("alpha")


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


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class TestWhereReportsCommitStatus:
    """`orglens-adapt`'s safety gate depends on this: it must see uncommitted
    paths or "no repository" before rewriting a driver document. The old
    single-repo `repo:` line was dropped when a unit grew several homes, so
    neither string it looked for could ever appear — the gate always
    passed, including exactly when it should have failed. This is one line
    per home rather than one line total, because a unit now spans several
    repositories.
    """

    def test_an_uncommitted_home_reports_its_count(self, runner, tmp_path):
        # `pytest`'s own `tmp_path` embeds the test's function name in the
        # directory it hands back — which, here, itself contains the word
        # "uncommitted" — so the assertion below checks for the exact count
        # rather than the bare word, or it would pass by finding its own
        # path rather than anything `where` printed.
        docs = tmp_path / "docs"
        proj = docs / "projects" / "clipcompose"
        _declare(proj, "clipcompose", "project")  # writes the marker itself
        _git("init", "-q", cwd=proj)
        (proj / "overview.md").write_text("# Overview\n")
        # Both the marker and overview.md are untracked after `git init`.

        result = runner.invoke(
            cli, ["where", "clipcompose"], env=_roots_config(tmp_path, [docs])
        )

        assert "2 uncommitted" in result.output

    def test_a_home_with_no_repository_says_nothing_is_backing_it_up(
        self, runner, tmp_path
    ):
        docs = tmp_path / "docs"
        proj = docs / "projects" / "clipcompose"
        _declare(proj, "clipcompose", "project")

        result = runner.invoke(
            cli, ["where", "clipcompose"], env=_roots_config(tmp_path, [docs])
        )

        assert "none — nothing is backing this up" in result.output

    def test_a_fully_committed_home_reports_clean(self, runner, tmp_path):
        docs = tmp_path / "docs"
        proj = docs / "projects" / "clipcompose"
        _declare(proj, "clipcompose", "project")
        (proj / "overview.md").write_text("# Overview\n")
        _git("init", "-q", cwd=proj)
        _git("config", "user.email", "a@b.c", cwd=proj)
        _git("config", "user.name", "a", cwd=proj)
        _git("add", "-A", cwd=proj)
        _git("commit", "-q", "-m", "init", cwd=proj)

        result = runner.invoke(
            cli, ["where", "clipcompose"], env=_roots_config(tmp_path, [docs])
        )

        assert "(clean)" in result.output

    def test_each_home_reports_its_own_repository(self, runner, tmp_path):
        """A unit spanning a committed code home and an uncommitted docs home
        must say so for *each*, not report on the first and go quiet about
        the rest.
        """
        docs = tmp_path / "traitful-docs" / "docs"
        code = tmp_path / "code"
        unit_docs = docs / "projects" / "orglens"
        unit_docs.mkdir(parents=True)
        (unit_docs / MARKER).write_text(
            "home: traitful-docs/docs/projects/orglens\n"
            "unit: orglens\nkind: project\n"
            "homes:\n  - orglens\n  - traitful-docs/docs/projects/orglens\n"
        )
        _git("init", "-q", cwd=docs.parent)  # the traitful-docs repo root
        (unit_docs / "overview.md").write_text("# Overview\n")  # left uncommitted
        code_home = code / "orglens"
        code_home.mkdir(parents=True)
        _git("init", "-q", cwd=code_home)
        _git("config", "user.email", "a@b.c", cwd=code_home)
        _git("config", "user.name", "a", cwd=code_home)
        (code / "traitful-docs" / "docs" / "projects" / "orglens").mkdir(parents=True)

        result = runner.invoke(
            cli, ["where", "orglens"], env=_roots_config(tmp_path, [docs, code])
        )

        # A wholly-new untracked directory collapses to one line under `git
        # status`, so this is "1 uncommitted" rather than one per file — the
        # count is not the point here, only that the docs home says so at
        # all while the code home separately says `(clean)`.
        assert "uncommitted" in result.output
        assert "(clean)" in result.output


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
        assert "owner collision" not in result.output

    def test_a_home_resolved_by_remote_only_names_an_owner_collision_not_a_rename(
        self, runner, tmp_path
    ):
        """The `name`-rung message ("renaming it will detach") is both false
        for a `remote`-rung home — it did not resolve by name, and renaming
        will not detach it — and it hides the real exposure: the remote rung
        matches only the repository-name tail, discarding the owner, so a
        different owner's repo of the same name resolves just as
        confidently. That exposure is only live when such a same-tail
        repository actually exists among the scanned candidates, so this
        gives it one — a second checkout under a different owner sharing
        `world-model-ladder` as its repository-name tail.
        """
        d = tmp_path / "renamed-locally"
        d.mkdir()
        _git("init", "-q", cwd=d)
        _git(
            "remote", "add", "origin",
            "git@github.com:saptaxis/world-model-ladder.git", cwd=d,
        )
        (d / MARKER).write_text(
            "unit: world-model-ladder\nkind: project\n"
            "homes:\n  - world-model-ladder\n"
        )
        rival = tmp_path / "other-owners-checkout"
        rival.mkdir()
        _git("init", "-q", cwd=rival)
        _git(
            "remote", "add", "origin",
            "git@github.com:someone-else/world-model-ladder.git", cwd=rival,
        )

        result = runner.invoke(cli, ["check"], env=_roots_config(tmp_path, [tmp_path]))

        assert (
            "world-model-ladder: home 'world-model-ladder' resolved by a git "
            "remote's repository name only — an owner collision would resolve "
            "silently" in result.output
        )
        assert "renaming it will detach" not in result.output

    def test_a_unique_remote_tail_names_no_owner_collision(self, runner, tmp_path):
        """The counterpart to the case above: with no other checkout sharing
        the repository-name tail, there is no owner to collide with, so
        `check` must stay quiet about it.
        """
        d = tmp_path / "renamed-locally"
        d.mkdir()
        _git("init", "-q", cwd=d)
        _git(
            "remote", "add", "origin",
            "git@github.com:saptaxis/world-model-ladder.git", cwd=d,
        )
        (d / MARKER).write_text(
            "unit: world-model-ladder\nkind: project\n"
            "homes:\n  - world-model-ladder\n"
        )

        result = runner.invoke(cli, ["check"], env=_roots_config(tmp_path, [tmp_path]))

        assert "owner collision" not in result.output

    def test_duplicate_unit_names_are_reported_with_their_declaring_paths(
        self, runner, tmp_path
    ):
        """A `cp -R`, a worktree, or a Dropbox conflicted copy can leave two
        markers both saying `unit: dup`. That must show up as a named row,
        not a crash — see `TestDuplicateDeclarations` below for the crash
        this used to cause everywhere else.
        """
        docs = tmp_path / "docs"
        a = docs / "projects" / "dup-a"
        b = docs / "projects" / "dup-b"
        _declare(a, "dup", "project")
        _declare(b, "dup", "project")
        env = _roots_config(tmp_path, [docs])

        result = runner.invoke(cli, ["check"], env=env)

        assert result.exit_code == 0
        assert "declared as a unit in more than one place" in result.output
        assert "dup-a" in result.output
        assert "dup-b" in result.output


class TestDuplicateDeclarations:
    """Two markers naming the same unit — a copy-pasted folder, a worktree, a
    Dropbox conflicted copy — used to raise `ValueError` out of a loop that
    passed an already-resolved `Unit.name` back into `Registry.resolve`,
    taking every command down for every unit, not only the duplicated one.
    """

    def test_status_survives_a_duplicated_unit_name(self, runner, tmp_path):
        docs = tmp_path / "docs"
        _declare(docs / "projects" / "dup-a", "dup", "project")
        _declare(docs / "projects" / "dup-b", "dup", "project")
        _declare(docs / "projects" / "unrelated", "unrelated", "project")
        env = _roots_config(tmp_path, [docs])

        result = runner.invoke(cli, ["status"], env=env)

        assert result.exit_code == 0
        assert "unrelated" in result.output

    def test_view_survives_a_duplicated_unit_name(self, runner, tmp_path):
        docs = tmp_path / "docs"
        _declare(docs / "projects" / "dup-a", "dup", "project")
        _declare(docs / "projects" / "dup-b", "dup", "project")
        env = _roots_config(tmp_path, [docs])
        out = tmp_path / "view.html"

        result = runner.invoke(cli, ["view", "--out", str(out), "--no-open"], env=env)

        assert result.exit_code == 0

    def test_snapshot_survives_a_duplicated_unit_name(self, runner, tmp_path):
        docs = tmp_path / "docs"
        _declare(docs / "projects" / "dup-a", "dup", "project")
        _declare(docs / "projects" / "dup-b", "dup", "project")
        env = _roots_config(tmp_path, [docs])

        result = runner.invoke(cli, ["snapshot", "--stdout"], env=env)

        assert result.exit_code == 0


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

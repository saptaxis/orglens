"""The snapshot cache kept fresh: a wider check, and a refresh nobody waits on."""

import os
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

import orglens.fresh as fresh
from orglens.cli import cli
from orglens.config import Config
from tests.test_cli import _roots_config, units_tree  # noqa: F401

#: The real one: conftest replaces `fresh.later` for every other test.
LATER = fresh.later


@pytest.fixture
def env(tmp_path, units_tree):  # noqa: F811
    return _roots_config(tmp_path, [units_tree])


@pytest.fixture
def written(env, units_tree):  # noqa: F811
    """The tree aged a minute, then a snapshot of it written: anything
    changed from here on is newer than the snapshot."""
    past = time.time() - 60
    for path in [units_tree, *units_tree.rglob("*")]:
        os.utime(path, (past, past))
    CliRunner().invoke(cli, ["snapshot"], env=env)
    return Config.from_yaml(Path(env["ORGLENS_CONFIG"]))


def _check(env):
    return CliRunner().invoke(cli, ["snapshot", "--check"], env=env)


def test_a_new_document_makes_it_stale(env, written, units_tree):  # noqa: F811
    assert _check(env).exit_code == 0
    (units_tree / "projects/orglens/plans").mkdir()
    (units_tree / "projects/orglens/plans/01-a-Oct212026.md").write_text("# A\n")
    result = _check(env)
    assert result.exit_code == 1
    assert "projects/orglens" in result.output


def test_an_edited_document_makes_it_stale(env, written, units_tree):  # noqa: F811
    spec = units_tree / "projects/clipcompose/specs/agent-integration.md"
    spec.write_text("# Agent integration, retitled\n")
    result = _check(env)
    assert result.exit_code == 1
    assert "agent-integration.md changed" in result.output


def test_a_deleted_document_makes_it_stale(env, written, units_tree):  # noqa: F811
    spec = units_tree / "projects/clipcompose/specs/agent-integration.md"
    spec.unlink()
    os.utime(spec.parent, (time.time() - 120, time.time() - 120))
    result = _check(env)
    assert result.exit_code == 1
    assert "is gone" in result.output


def test_if_stale_writes_only_when_stale_and_lets_go_of_the_lock(env, written):
    lock = fresh.lock_path(written)
    lock.touch()
    before = written.snapshot_path.stat().st_mtime
    CliRunner().invoke(cli, ["snapshot", "--if-stale"], env=env)
    assert written.snapshot_path.stat().st_mtime == before
    assert not lock.exists()

    written.snapshot_json_path.unlink()
    CliRunner().invoke(cli, ["snapshot", "--if-stale"], env=env)
    assert written.snapshot_json_path.exists()


class TestLater:
    @pytest.fixture
    def spawned(self, monkeypatch):
        calls = []
        monkeypatch.setattr(fresh.subprocess, "Popen", lambda argv, **kw: calls.append(argv))
        return calls

    def test_it_starts_one_detached_refresh(self, written, spawned):
        LATER(written)
        LATER(written)
        assert len(spawned) == 1
        assert spawned[0][-3:] == ["orglens", "snapshot", "--if-stale"]
        assert fresh.lock_path(written).exists()

    def test_a_lock_left_by_a_refresh_that_died_is_taken(self, written, spawned):
        lock = fresh.lock_path(written)
        lock.touch()
        old = time.time() - fresh.LOCK_EXPIRES_S - 1
        os.utime(lock, (old, old))
        LATER(written)
        assert len(spawned) == 1

    def test_it_never_raises(self, written, monkeypatch):
        def boom(*a, **kw):
            raise OSError("no")
        monkeypatch.setattr(fresh.subprocess, "Popen", boom)
        LATER(written)

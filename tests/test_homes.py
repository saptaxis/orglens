import subprocess
from pathlib import Path

from orglens.declaration import MARKER
from orglens.homes import Candidate, normalise_remote, resolve_home, scan_roots


def test_normalise_remote_strips_host_alias_and_suffix():
    # This machine's traitful-docs remote uses a host alias, so URLs are not
    # canonical across setups and only the owner/repo tail is comparable.
    assert normalise_remote(
        "git@github.com-traitful:traitful-ai/traitful-docs.git"
    ) == "traitful-ai/traitful-docs"
    assert normalise_remote(
        "git@github.com:saptaxis/world-model-ladder.git"
    ) == "saptaxis/world-model-ladder"
    assert normalise_remote(
        "https://github.com/saptaxis/orglens"
    ) == "saptaxis/orglens"
    assert normalise_remote("") is None


def test_marker_wins_over_directory_name(tmp_path):
    d = tmp_path / "some-checkout-name"
    d.mkdir()
    (d / MARKER).write_text("home: world-model-ladder\n")
    candidates = scan_roots([tmp_path])
    home = resolve_home("world-model-ladder", candidates)
    assert home.path == d
    assert home.how == "marker"


def test_remote_answers_when_no_marker(tmp_path):
    d = tmp_path / "renamed-locally"
    d.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin",
         "git@github.com:saptaxis/world-model-ladder.git"],
        cwd=d, check=True,
    )
    candidates = scan_roots([tmp_path])
    home = resolve_home("world-model-ladder", candidates)
    assert home.path == d
    assert home.how == "remote"


def test_directory_name_is_the_last_rung(tmp_path):
    d = tmp_path / "world-model-ladder"
    d.mkdir()
    candidates = scan_roots([tmp_path])
    home = resolve_home("world-model-ladder", candidates)
    assert home.path == d
    assert home.how == "name"


def test_a_home_not_on_this_machine_is_absent_not_an_error(tmp_path):
    candidates = scan_roots([tmp_path])
    home = resolve_home("latent-world-geometry", candidates)
    assert home.path is None
    assert home.how == "absent"


def test_subpath_is_joined_onto_the_repository(tmp_path):
    repo = tmp_path / "traitful-docs"
    (repo / "docs" / "projects" / "orglens").mkdir(parents=True)
    candidates = scan_roots([tmp_path])
    home = resolve_home("traitful-docs/docs/projects/orglens", candidates)
    assert home.path == repo / "docs" / "projects" / "orglens"
    assert home.how == "name"


def test_scan_does_not_descend_into_dot_directories(tmp_path):
    hidden = tmp_path / ".cache" / "world-model-ladder"
    hidden.mkdir(parents=True)
    candidates = scan_roots([tmp_path])
    assert all(".cache" not in c.path.parts for c in candidates)


def test_a_subpath_that_does_not_exist_is_absent(tmp_path):
    (tmp_path / "traitful-docs").mkdir()
    home = resolve_home("traitful-docs/docs/projects/orglens", scan_roots([tmp_path]))
    assert home.path is None
    assert home.how == "absent"


def test_a_directory_declared_elsewhere_does_not_shadow_a_coincidental_name(tmp_path):
    # A docs checkout and a code checkout can share a leaf name — that is the
    # ordinary case, not an edge case. The docs folder here has already named
    # itself something else via marker, so it must not answer for "orglens"
    # just because its basename happens to match.
    decoy = tmp_path / "decoy_root" / "orglens"
    decoy.mkdir(parents=True)
    (decoy / MARKER).write_text(
        "home: something-else\nunit: something-else\nkind: project\n"
        "homes:\n  - something-else\n"
    )
    real = tmp_path / "real_root" / "orglens"
    real.mkdir(parents=True)

    candidates = scan_roots([tmp_path / "decoy_root", tmp_path / "real_root"])
    home = resolve_home("orglens", candidates)
    assert home.path == real
    assert home.how == "name"


def test_a_root_reached_through_a_symlink_yields_resolved_paths(tmp_path):
    # ~/Dropbox is a symlink to ~/Library/CloudStorage/Dropbox, and sessions
    # record the resolved form. A candidate discovered through the symlink
    # must come back resolved, or every later comparison misses — silently.
    real = tmp_path / "real"
    (real / "world-model-ladder").mkdir(parents=True)
    link = tmp_path / "via-symlink"
    link.symlink_to(real)

    home = resolve_home("world-model-ladder", scan_roots([link]))
    assert home.path == (real / "world-model-ladder").resolve()
    assert "via-symlink" not in home.path.parts

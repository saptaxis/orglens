import subprocess
from pathlib import Path

from orglens.declaration import MARKER
from orglens.homes import (
    Candidate,
    candidates_for,
    normalise_remote,
    repo_of,
    resolve_home,
    scan_roots,
)


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


def test_a_marker_claiming_the_full_name_is_not_double_joined(tmp_path):
    # A marker may name the whole home, subpath included. Joining the subpath
    # again would point at a directory that does not exist — and the existence
    # check would then report a home that is plainly there as absent.
    #
    # Rooted *at* traitful-docs rather than above it: scan_roots never yields
    # a root as its own candidate, so no directory is literally named
    # "traitful-docs" to rescue a broken match via the name rung. That rescue
    # is what let this bug hide inside the two-root fixture in units.py.
    deep = tmp_path / "traitful-docs" / "docs" / "projects" / "orglens"
    deep.mkdir(parents=True)
    (deep / MARKER).write_text("home: traitful-docs/docs/projects/orglens\n")

    home = resolve_home(
        "traitful-docs/docs/projects/orglens",
        scan_roots([tmp_path / "traitful-docs"]),
    )
    assert home.path == deep
    assert home.how == "marker"


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


def test_candidates_for_names_every_directory_that_could_have_won(tmp_path):
    """`resolve_home` has to pick one path and does — by scan order. That
    hides a real tie: two docs checkouts named the same thing, where the
    real code home's plans go invisible with only a `weak` row as a clue.
    `candidates_for` is what lets `check` say the tie existed at all.
    """
    a = tmp_path / "root-a" / "alpha"
    b = tmp_path / "root-b" / "alpha"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    candidates = scan_roots([tmp_path / "root-a", tmp_path / "root-b"])

    rivals = candidates_for("alpha", candidates)

    assert {c.path for c in rivals} == {a, b}


def test_candidates_for_names_one_when_resolution_is_unambiguous(tmp_path):
    d = tmp_path / "world-model-ladder"
    d.mkdir()
    candidates = scan_roots([tmp_path])

    assert [c.path for c in candidates_for("world-model-ladder", candidates)] == [d]


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


def test_a_nested_root_reaches_past_the_outer_root_depth_bound(tmp_path):
    # With `docs` and `docs/research/prog` both listed, a marker at
    # `docs/research/prog/articles/piece` is depth 4 from the first root and
    # depth 2 from the second. It has to be found: the setup note prescribes
    # adding the nested root as the remedy for anything past the bound.
    docs = tmp_path / "docs"
    prog = docs / "research" / "prog"
    piece = prog / "articles" / "piece"
    piece.mkdir(parents=True)
    (piece / MARKER).write_text("home: piece\n")

    candidates = scan_roots([docs, prog])
    assert resolve_home("piece", candidates).how == "marker"


def test_overlapping_roots_report_each_directory_once(tmp_path):
    docs = tmp_path / "docs"
    prog = docs / "research" / "prog"
    prog.mkdir(parents=True)

    candidates = scan_roots([docs, prog])
    paths = [c.path for c in candidates]
    assert len(paths) == len(set(paths))


def test_repo_of_is_the_first_segment_of_a_home_name():
    # `traitful-docs/docs/projects/orglens` is a subpath inside the
    # `traitful-docs` repository; a bare name is its own repository.
    assert repo_of("traitful-docs/docs/projects/orglens") == "traitful-docs"
    assert repo_of("orglens") == "orglens"


def test_a_remote_is_read_from_git_config_without_running_git(tmp_path, monkeypatch):
    # The sweep runs once per command over every checkout under the roots;
    # a subprocess per checkout was 1.4s of a 9s `status`. The URL is in
    # `.git/config`, which is a file.
    import subprocess as sp
    from orglens import homes
    d = tmp_path / "some-checkout"
    (d / ".git").mkdir(parents=True)
    (d / ".git" / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n"
        "[remote \"origin\"]\n\turl = git@github.com:saptaxis/world-model-ladder.git\n"
        "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
    )
    monkeypatch.setattr(sp, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("git was run")))

    assert homes._remote_of(d) == "saptaxis/world-model-ladder"


def test_a_checkout_without_an_origin_has_no_remote(tmp_path):
    from orglens import homes
    d = tmp_path / "local-only"
    (d / ".git").mkdir(parents=True)
    (d / ".git" / "config").write_text("[core]\n\tbare = false\n")
    assert homes._remote_of(d) is None


def test_a_root_that_is_itself_a_repository_is_a_candidate(tmp_path):
    # `~/Dropbox/dotfiles` has no useful parent to list as a root — its
    # parent holds everything. Listing the checkout itself must work.
    repo = tmp_path / "dotfiles"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text('[remote "origin"]\n\turl = git@github.com:me/dotfiles.git\n')
    candidates = scan_roots([repo])
    home = resolve_home("dotfiles", candidates)
    assert home.path == repo
    assert home.how == "remote"


def test_a_root_that_is_a_plain_directory_is_not_its_own_candidate(tmp_path):
    # A documents root is a container, not a home; making it a candidate
    # would let its own basename answer for a home by coincidence.
    docs = tmp_path / "docs"
    (docs / "projects").mkdir(parents=True)
    assert all(c.path != docs for c in scan_roots([docs]))

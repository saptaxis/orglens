"""Which folders a walk never enters: one rule for every walk."""

from orglens import skip


def test_hidden_folders_and_the_default_names_are_skipped():
    assert skip.skipped(".git")
    assert skip.skipped("node_modules")
    assert skip.skipped("orglens.egg-info")


def test_ordinary_folders_are_not_skipped():
    assert not skip.skipped("src")
    assert not skip.skipped("docs")


def test_names_match_case_sensitively_on_every_machine():
    # macOS's `fnmatch` folds case; `Build` must not match `build` there
    # and miss it elsewhere.
    assert not skip.skipped("Build")


def test_use_replaces_the_default():
    skip.use(["data"])
    assert skip.skipped("data")
    assert not skip.skipped("node_modules")


def test_an_empty_list_skips_only_hidden_folders():
    skip.use([])
    assert skip.skipped(".venv")
    assert not skip.skipped("node_modules")


def test_descend_refuses_a_link_a_file_and_a_skipped_folder(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    (tmp_path / "file.txt").write_text("")
    (tmp_path / "build").mkdir()

    assert skip.descend(real)
    assert not skip.descend(tmp_path / "link")
    assert not skip.descend(tmp_path / "file.txt")
    assert not skip.descend(tmp_path / "build")

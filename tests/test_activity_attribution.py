from orglens import activity
from orglens.sessions import Session
from tests.conftest import scad_index


def test_the_index_location_is_read_when_called_not_when_imported(tmp_path, monkeypatch):
    # `index` defaulted to `SCAD_INDEX` in the signature, which bound the real
    # `~/.scad/index.sqlite` at import time, so a caller that passed nothing
    # (`list`, `status`, `view`) could not be pointed anywhere else by a test.
    # `needs` is read from the index by id, so it only appears if the
    # reassigned location was the one opened.
    home = tmp_path / "orglens"
    home.mkdir()
    index = scad_index(tmp_path, [
        {"id": "s1", "kind": "main", "agent": "claude", "machine": "m",
         "cwd": str(home), "n_turns": 1, "grade": "", "source": "",
         "needs": "which way?"},
    ])
    monkeypatch.setattr(activity, "SCAD_INDEX", index)
    s = Session(id="s1", agent="claude", cwd=str(home), started=None, ended=None,
                turns=1, label=None, outcome=None, live=False,
                units=frozenset({"orglens"}), how="containment")

    assert activity.read([home], "orglens", sessions=[s]).needs == [
        {"question": "which way?", "at": None}
    ]

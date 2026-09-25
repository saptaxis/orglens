

def test_an_unattributed_row_carries_the_commands_that_act_on_it():
    """Seeing the pile was never the hard part: acting on a row meant
    retyping a uuid into another terminal."""
    from orglens.sessions import Session
    from orglens.view import _unattributed

    loose = [Session(id="abcd1234-full-id", agent="claude", cwd="/x/scratch/one",
                     started=None, ended=1000_000, turns=3, label="stray",
                     outcome=None, live=False, units=frozenset(), how=None)]
    html_out = _unattributed(loose)
    assert "orglens attribute abcd1234-full-id " in html_out
    assert "orglens dismiss abcd1234-full-id" in html_out
    assert "orglens dismiss --under /x/scratch" in html_out
    assert "scad session resume abcd1234-full-id --print" in html_out


def test_no_unit_is_proposed_on_an_unattributed_row():
    """A session here is contained in no home, so the cwd suggests nothing by
    construction. The attribute command is offered unfinished."""
    from orglens.sessions import Session
    from orglens.view import _unattributed

    loose = [Session(id="abcd1234-full-id", agent="claude", cwd="/x/scratch/one",
                     started=None, ended=1000_000, turns=3, label="orglens work",
                     outcome=None, live=False, units=frozenset(), how=None)]
    html_out = _unattributed(loose)
    assert "attribute abcd1234-full-id orglens" not in html_out

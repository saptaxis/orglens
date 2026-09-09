import json

from orglens.events import Event, append, attributions, read_all


def test_an_event_round_trips(tmp_path):
    append(Event(kind="attributed", unit="orglens", session="s1", at=100,
                 machine="ribosome"), root=tmp_path)
    got = read_all(root=tmp_path)
    assert len(got) == 1
    assert got[0].unit == "orglens"
    assert got[0].session == "s1"
    assert got[0].kind == "attributed"


def test_events_shard_per_session_so_two_writers_never_share_a_file(tmp_path):
    append(Event("attributed", "a", "s1", 100, "ribosome"), root=tmp_path)
    append(Event("attributed", "b", "s2", 101, "ribosome"), root=tmp_path)
    files = sorted(p.name for p in tmp_path.rglob("*.jsonl"))
    assert files == ["s1.jsonl", "s2.jsonl"]


def test_an_event_with_no_session_shards_by_machine(tmp_path):
    append(Event("created", "orglens", None, 100, "ribosome"), root=tmp_path)
    assert [p.name for p in tmp_path.rglob("*.jsonl")] == ["ribosome.jsonl"]


def test_reading_sorts_by_time_across_shards(tmp_path):
    append(Event("attributed", "b", "s2", 200, "ribosome"), root=tmp_path)
    append(Event("attributed", "a", "s1", 100, "ribosome"), root=tmp_path)
    assert [e.unit for e in read_all(root=tmp_path)] == ["a", "b"]


def test_the_latest_attribution_wins_and_the_change_of_mind_survives(tmp_path):
    append(Event("attributed", "wrong-guess", "s1", 100, "ribosome"), root=tmp_path)
    append(Event("attributed", "corrected", "s1", 200, "ribosome"), root=tmp_path)
    assert attributions(root=tmp_path) == {"s1": "corrected"}
    # Both are still on disk: a file merge would have to pick one and lose the
    # other, and an append-only log keeps the disagreement visible.
    assert len(read_all(root=tmp_path)) == 2


def test_a_missing_directory_is_empty_not_an_error(tmp_path):
    assert read_all(root=tmp_path / "absent") == []
    assert attributions(root=tmp_path / "absent") == {}


def test_a_malformed_line_is_skipped_not_fatal(tmp_path):
    append(Event("attributed", "good", "s1", 100, "ribosome"), root=tmp_path)
    (tmp_path / "s1.jsonl").open("a").write("not json\n")
    assert [e.unit for e in read_all(root=tmp_path)] == ["good"]


def test_an_event_never_records_a_path(tmp_path):
    # A path makes an event untrue on the machine that reads it.
    append(Event("attributed", "orglens", "s1", 100, "ribosome"), root=tmp_path)
    written = json.loads((tmp_path / "s1.jsonl").read_text().strip())
    assert set(written) == {"kind", "unit", "session", "at", "machine"}

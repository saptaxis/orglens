from __future__ import annotations

from pathlib import Path

from orglens.workflow.predicates import STATIC_PREDICATES, evaluate, predicate_names
from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "brief": "*-brief.md",
    "artifact": {"family": "draft", "canonical": "draft.md"},
    "nodes": {
        "brief": {"mutates": True},
        "draft": {"mutates": True},
        "critique": {"diagnoses": True},
        "revise": {"mutates": True},
        "audit": {"diagnoses": True},
    },
}


def facts(tmp_path: Path) -> dict[str, bool]:
    return evaluate(read_packet(tmp_path, WORKFLOW), WORKFLOW)


def log(tmp_path: Path, *nodes: str) -> None:
    (tmp_path / "runs.jsonl").write_text(
        "".join(
            '{"type":"node_completed","node":"%s","at":"t","event_id":"%d"}\n' % (n, i)
            for i, n in enumerate(nodes)
        )
    )


def content(tmp_path: Path) -> None:
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")


def test_the_static_set_is_four():
    assert len(STATIC_PREDICATES) == 4


def test_the_generated_names_come_from_the_deck():
    assert predicate_names(WORKFLOW) == STATIC_PREDICATES | {
        "awaiting_mutation",
        "last_diagnostic_is_critique",
        "last_diagnostic_is_audit",
    }


def test_a_deck_with_different_node_names_gets_different_predicates():
    """The engine knows no node names of its own."""
    other = {"nodes": {"inspect": {"diagnoses": True}, "fix": {"mutates": True}}}
    assert "last_diagnostic_is_inspect" in predicate_names(other)
    assert not any("critique" in n for n in predicate_names(other))


def test_every_declared_predicate_is_returned(tmp_path: Path):
    assert set(facts(tmp_path)) == set(predicate_names(WORKFLOW))


def test_empty_packet(tmp_path: Path):
    f = facts(tmp_path)
    assert f["brief_exists"] is False
    assert f["artifact_exists"] is False
    assert f["awaiting_mutation"] is False


def test_brief_and_artifact(tmp_path: Path):
    content(tmp_path)
    f = facts(tmp_path)
    assert f["brief_exists"] and f["artifact_exists"]
    assert f["artifact_noncanonical"] is False


def test_noncanonical_artifact(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft-v2.md").write_text("prose")
    assert facts(tmp_path)["artifact_noncanonical"] is True


def test_published_frontmatter(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("---\npublished: https://x/y\n---\n")
    assert facts(tmp_path)["brief_published"] is True


def test_a_diagnostic_since_the_last_mutation(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "draft", "critique")
    f = facts(tmp_path)
    assert f["awaiting_mutation"] is True
    assert f["last_diagnostic_is_critique"] is True
    assert f["last_diagnostic_is_audit"] is False


def test_a_mutation_since_the_last_diagnostic(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "draft", "critique", "revise")
    f = facts(tmp_path)
    assert f["awaiting_mutation"] is False
    assert f["last_diagnostic_is_critique"] is True


def test_the_last_diagnostic_survives_a_mutation(tmp_path: Path):
    """Which diagnostic ran last is what makes the cycle alternate."""
    content(tmp_path)
    log(tmp_path, "draft", "critique", "revise", "audit", "revise")
    f = facts(tmp_path)
    assert f["awaiting_mutation"] is False
    assert f["last_diagnostic_is_audit"] is True
    assert f["last_diagnostic_is_critique"] is False


def test_no_diagnostic_yet(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft")
    f = facts(tmp_path)
    assert f["awaiting_mutation"] is False
    assert f["last_diagnostic_is_critique"] is False
    assert f["last_diagnostic_is_audit"] is False

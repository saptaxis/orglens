"""A workflow is an ordered list of nodes. Loading it is the whole validation."""

from pathlib import Path

import pytest

from orglens.workflow.definition import WorkflowError, load_workflow


def _definition(tmp_path: Path, text: str, programs=("a.md", "b.md")) -> Path:
    for c in programs:
        (tmp_path / "programs").mkdir(exist_ok=True)
        (tmp_path / "programs" / c).write_text("# program\n")
    path = tmp_path / "WORKFLOW.yaml"
    path.write_text(text)
    return path


GOOD = """\
workflow: demo
nodes:
  - name: first
    program: programs/a.md
    writes: one.md
  - name: second
    program: programs/b.md
    writes: two.md
    review: true
"""


def test_a_workflow_loads_its_nodes_in_order_with_programs_resolved(tmp_path):
    workflow = load_workflow(_definition(tmp_path, GOOD))
    assert workflow.name == "demo"
    assert [s.name for s in workflow.nodes] == ["first", "second"]
    assert workflow.nodes[0].program == (tmp_path / "programs" / "a.md").resolve()
    assert workflow.nodes[0].writes == "one.md"
    assert workflow.nodes[0].review is False
    assert workflow.nodes[1].review is True
    assert workflow.path == tmp_path / "WORKFLOW.yaml"


def test_nodes_are_reachable_by_name_and_by_position(tmp_path):
    workflow = load_workflow(_definition(tmp_path, GOOD))
    assert workflow.node("second").writes == "two.md"
    assert workflow.node("nope") is None
    assert workflow.after("first").name == "second"
    assert workflow.after("second") is None


def test_empty_nodes_are_refused(tmp_path):
    with pytest.raises(WorkflowError, match="no nodes"):
        load_workflow(_definition(tmp_path, "workflow: x\nnodes: []\n"))


def test_duplicate_names_are_refused(tmp_path):
    text = GOOD.replace("name: second", "name: first")
    with pytest.raises(WorkflowError, match="first"):
        load_workflow(_definition(tmp_path, text))


def test_a_missing_program_is_refused_at_load(tmp_path):
    text = GOOD.replace("programs/b.md", "programs/missing.md")
    with pytest.raises(WorkflowError, match="missing.md"):
        load_workflow(_definition(tmp_path, text))


def test_a_node_without_writes_is_refused(tmp_path):
    text = GOOD.replace("    writes: two.md\n", "")
    with pytest.raises(WorkflowError, match="second"):
        load_workflow(_definition(tmp_path, text))


def test_a_node_without_a_name_is_refused(tmp_path):
    text = GOOD.replace("  - name: second\n", "  - ")
    with pytest.raises(WorkflowError, match="name"):
        load_workflow(_definition(tmp_path, text))


def test_a_missing_file_is_a_workflow_error_not_a_crash(tmp_path):
    with pytest.raises(WorkflowError, match="WORKFLOW.yaml"):
        load_workflow(tmp_path / "WORKFLOW.yaml")

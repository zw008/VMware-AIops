"""Regression — the error-actionability grader must not credit phantom tools.

The ``names_artifact`` dimension used to match on the prefixes ``list_`` and
``get_``, which made it blind in both directions. It scored zero for real tools
named anything else (``cluster_info``, ``browse_datastore``, ``vm_info``), and
it scored full marks for names that do not exist — vmware-monitor shipped an
error telling the model to run ``list_vms``, a tool with no such name on the
surface, and the rubric called that a well-taught error.

That second half is the one worth a regression test. A grader that rewards
pointing at an imaginary tool actively selects for the failure it claims to
measure: the message reads as helpful, scores as helpful, and strands the model
on a call it cannot make.

These run against a fabricated tool list rather than the live registry on
purpose. The property under test is "only names actually on the surface count",
and passing the surface in explicitly is what makes that property visible —
against the real registry the test would drift every time a tool is added.
"""

from __future__ import annotations

from types import SimpleNamespace

from ..capability.test_error_actionability import _artifact_matcher

SURFACE = ("cluster_info", "list_virtual_machines", "vm_power_on")


def _names_artifact(text: str) -> bool:
    return _artifact_matcher([SimpleNamespace(name=n) for n in SURFACE])(text)


def test_credits_a_tool_that_is_on_the_surface():
    assert _names_artifact("Host not in cluster. Run cluster_info to see its members.")


def test_credits_a_tool_whose_name_has_no_list_or_get_prefix():
    """The original blind spot: a real tool the prefix heuristic could not see."""
    assert _names_artifact("Not found. Run vm_power_on after checking the state.")


def test_rejects_a_tool_that_is_not_on_the_surface():
    assert not _names_artifact("VM not found. Run list_vms to see available VMs.")


def test_rejects_a_name_that_merely_extends_a_real_tool():
    """Substring matching would credit this; word boundaries are why it does not."""
    assert not _names_artifact("Run cluster_infos to see members.")


def test_rejects_a_truncated_real_tool_name():
    assert not _names_artifact("Run cluster_inf to see members.")


def test_credits_a_companion_skill_handoff():
    """Routing to a sibling skill is a followable instruction, not a dead end."""
    assert _names_artifact("Run 'vmware-storage iscsi status esx-01' (vmware-storage skill).")


def test_rejects_an_unrelated_command():
    assert not _names_artifact("Run 'kubectl rollout status' and retry.")


def test_rejects_a_remedy_that_names_nothing():
    assert not _names_artifact("Verify connectivity and retry the operation.")

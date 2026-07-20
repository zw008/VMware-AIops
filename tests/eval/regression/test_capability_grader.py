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

from ..capability._skill import CLI_NAME
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


# ── a cited CLI command must exist, like a cited tool ────────────────────────
#
# Tool names were checked against the live registry while CLI invocations were
# taken on faith, so one skill shipped thirteen hints telling the model to run
# `<cli> doctor` — a command it does not have; the real one is `check`. Every
# one scored full marks, which made the fix and the phantom worth the same.

#: Full runnable paths, as the click tree reports them. `pool` is a group and
#: appears only as a prefix — never as a command you can run on its own.
REAL_COMMANDS = frozenset({"check", "status", "init", "pool members", "pool enable"})


def _with_commands(text: str, commands=REAL_COMMANDS) -> bool:
    return _artifact_matcher(
        [SimpleNamespace(name=n) for n in SURFACE], cli_commands=commands
    )(text)


def test_credits_a_cli_command_that_exists():
    assert _with_commands(f"Run '{CLI_NAME} check' to verify connectivity.")


def test_rejects_a_cli_command_that_does_not_exist():
    assert not _with_commands(f"Run '{CLI_NAME} not-a-command' to verify connectivity.")


def test_a_companion_prefix_does_not_credit_this_skill_naming_itself():
    """``vmware-nsx`` is a companion; ``vmware-nsx-security`` is not its own.

    Substring matching let the longer-named skill score a "documented hand-off"
    on every mention of itself, which also meant its own CLI citations were
    never checked against its own command tree — the phantom check silently
    did not apply to one member of the family.
    """
    assert not _with_commands(f"Run '{CLI_NAME} not-a-command' to fix it.")


def test_credits_a_real_subcommand_under_a_group():
    assert _with_commands(f"Run '{CLI_NAME} pool members web-pool' to list them.")


def test_rejects_a_phantom_subcommand_under_a_real_group():
    """Checking only the first token accepted this, because the group is real.

    An agent writing family error messages produced exactly this string, caught
    it by hand against `--help`, and reported that the rubric had not. A check
    that validates a prefix of the claim is not validating the claim.
    """
    assert not _with_commands(f"Run '{CLI_NAME} pool list' to see pools.")


def test_credits_a_command_followed_by_prose():
    """Real messages trail words that are not arguments."""
    assert _with_commands(f"Run '{CLI_NAME} init' to rebuild the config file.")


def test_credits_a_bare_cli_mention():
    """Naming the executable is followable even without a subcommand."""
    assert _with_commands(f"Install {CLI_NAME} and retry.")


def test_a_tool_reference_after_the_cli_name_is_not_a_subcommand_claim():
    """Subcommands are kebab-case, tools are snake_case.

    "run 'vmware-monitor list_virtual_machines'" cites a tool, and reading the
    first word as a phantom command named "list" would refute a perfectly good
    hand-off.
    """
    assert _with_commands(f"Run '{CLI_NAME} list_virtual_machines' and copy a name.")


def test_unresolvable_cli_is_not_treated_as_refuted():
    """An app we cannot introspect makes the claim unverifiable, not false."""
    assert _with_commands(f"Run '{CLI_NAME} not-a-command' to verify.", commands=None)


# ── flags and env vars ──────────────────────────────────────────────────────


def test_credits_a_real_long_flag():
    assert _names_artifact("Pass --target to select a vCenter.")


def test_rejects_a_bare_double_hyphen():
    """``--`` used to be a static marker, so any em-dash-ish text scored free."""
    assert not _names_artifact("The operation failed -- try again later.")


def test_credits_a_named_env_var():
    assert _names_artifact("Password not found. Set VMWARE_PROD_PASSWORD and retry.")


# ── guidance assembled at runtime must be read, not blanked ─────────────────
#
# Every f-string hole used to render as `{}`, so a hint hoisted into a module
# constant or produced by a helper scored as naming nothing. Four skills hit
# this independently, and all four drew the same conclusion: the rubric was
# pushing them to duplicate an inline literal instead of sharing a constant —
# rewarding the worse pattern. Resolving holes is what stops that.

import ast  # noqa: E402 — grouped with the tests that use it

from ..capability.test_error_actionability import _messages_in_tree


def _messages(src: str):
    return list(_messages_in_tree(ast.parse(src), "sample.py"))


def test_resolves_a_hint_hoisted_into_a_module_constant():
    (_f, _ln, text, _holes, composed), = _messages(
        '_HINT = "Run cluster_info to see members."\n'
        'def f():\n'
        '    raise ValueError(f"Host {name} unknown. {_HINT}")\n'
    )
    assert "cluster_info" in text
    assert composed is False, "a constant resolves exactly; nothing is approximated"


def test_folds_in_the_strings_a_hint_helper_can_return():
    (_f, _ln, text, _holes, composed), = _messages(
        'def _hint(status):\n'
        '    if status == 404:\n'
        '        return "Run list_virtual_machines and copy an exact name."\n'
        '    return "Check the controller."\n'
        'def g(status):\n'
        '    raise ValueError(f"Request failed. {_hint(status)}")\n'
    )
    assert "list_virtual_machines" in text
    assert composed is True, "only some branches name a tool — the credit is an upper bound"


# ── the cap the agent actually reads through ───────────────────────────────
#
# `_safe_error` truncates with no ellipsis, so a cut is invisible. One skill was
# found shipping a 396-character message whose closing remedy had never once
# been delivered, while the rubric scored it a perfectly taught error. These run
# on fabricated messages because a repo with nothing over budget would pass this
# check without exercising a line of it.

from ..capability.test_error_actionability import _truncation_findings

_TAUGHT = {"names_input": True, "states_remedy": True, "names_artifact": True}
_BARE = {"names_input": True, "states_remedy": False, "names_artifact": False}


def _graded(text, grade=_TAUGHT):
    return [("f.py", 1, text, False, grade)]


def test_flags_a_message_longer_than_the_cap():
    over, _ = _truncation_findings(_graded("Run list_vms. " + "x" * 400), budget=300)
    assert over and over[0]["chars"] > 300


def test_accepts_a_message_within_the_cap():
    over, _ = _truncation_findings(_graded("Not found. Run cluster_info."), budget=300)
    assert not over


def test_ignores_messages_with_no_remedy_to_lose():
    over, _ = _truncation_findings(_graded("x" * 400, grade=_BARE), budget=300)
    assert not over


def test_does_not_charge_a_composed_message_for_every_folded_branch():
    """Folded branches are a content view, not a length.

    The first run of this check reported a 759-character message in a repo whose
    longest real message is a third of that — the union of one helper's branches,
    none of which is ever emitted whole.
    """
    graded = [("f.py", 1, "Run cluster_info. " + "x" * 400, True, _TAUGHT)]
    over, _ = _truncation_findings(graded, budget=300)
    assert not over


def test_flags_a_remedy_that_trails_an_interpolation():
    """A short template still loses its remedy when the value runs long."""
    _, at_risk = _truncation_findings(_graded("Failed: {}. Run cluster_info."), budget=300)
    assert at_risk == ["f.py:1"]


def test_does_not_flag_a_remedy_placed_before_the_interpolation():
    """Putting the remedy first is the fix; it must read as safe."""
    _, at_risk = _truncation_findings(_graded("Run cluster_info. Detail: {}"), budget=300)
    assert not at_risk


def test_unresolvable_holes_still_render_as_placeholders():
    (_f, _ln, text, holes, composed), = _messages(
        'def h(vm):\n'
        '    raise ValueError(f"VM {vm} not found.")\n'
    )
    assert text == "VM {} not found."
    assert holes is True and composed is False

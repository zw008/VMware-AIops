"""Capability — how much of a small model's context is gone before it starts?

What this measures
------------------
Every tool's name, description, and JSON schema is serialised into the model's
context on *every* turn, whether or not the tool is ever called. This eval
measures that fixed cost and expresses it as the headroom left in a reference
context window.

Why it matters for a small model
--------------------------------
This is the one context cost an operator cannot page away. CLAUDE.md's context
budgeting reasons about response sizes and about the ~800-token-per-skill
description layer, but the tool manifest is larger than both and had never been
measured. The operator in VMware-AIops issue #31 was driving the family with a
locally hosted Llama 3.3 70B; local deployments of that class are routinely run
at 8k or 16k context to fit available VRAM, not at the nominal maximum. At 16k,
a 10k manifest means the model has already spent two thirds of everything it
has before reading the user's question — and the observed failure ("omits
existing information, or incorrectly states that no data was returned") is
exactly what a model does when it is out of room.

So the headroom number here is not housekeeping. It is an upper bound on how
much conversation, tool output, and reasoning the skill can afford to leave for
the model that most needs it.

The reference budget
--------------------
16,384 tokens — the middle of the band local 70B-class deployments actually run
at, and the point where the tradeoff is real rather than either trivially fine
(128k) or hopeless (4k). It is a fixed yardstick, not a claim about any specific
deployment; its job is to make two releases comparable.

How to read the score
---------------------
``manifest_context_headroom`` is the percentage of the reference window still
free after the manifest loads. **>80%** the surface is cheap; **60–80%** healthy;
**40–60%** the surface is a significant tax and growth should be deliberate;
**<40%** small-model use is compromised and tools should be merged or
descriptions tightened. Rising tool counts push this down mechanically, so read
it together with ``mean_tokens_per_tool``:
falling headroom with flat per-tool cost is healthy growth, falling headroom with
rising per-tool cost is bloat.
"""

from __future__ import annotations

import json

import pytest

from ._scoring import Score, estimate_tokens

pytestmark = pytest.mark.capability

#: See "The reference budget" in the module docstring.
REFERENCE_CONTEXT = 16_384

#: Per-tool ceiling. Above this a description has usually stopped explaining the
#: tool and started duplicating reference material that belongs in
#: references/capabilities.md, where the model loads it only on demand.
PER_TOOL_CEILING = 350


def _tool_tokens(tool) -> int:
    return (
        estimate_tokens(tool.name)
        + estimate_tokens(tool.description or "")
        + estimate_tokens(json.dumps(tool.inputSchema or {}, sort_keys=True))
    )


def test_manifest_context_headroom(board, tools):
    """Record the free share of a reference small-model window after the manifest."""
    per_tool = {t.name: _tool_tokens(t) for t in tools}
    manifest = sum(per_tool.values())
    headroom = max(0, REFERENCE_CONTEXT - manifest)

    heaviest = sorted(per_tool.items(), key=lambda kv: -kv[1])[:5]
    score = board.add(
        Score(
            name="manifest_context_headroom",
            value=headroom,
            maximum=REFERENCE_CONTEXT,
            unit="tokens",
            detail={
                "reference_context": REFERENCE_CONTEXT,
                "manifest_tokens": manifest,
                "tool_count": len(per_tool),
                "mean_tokens_per_tool": round(manifest / max(1, len(per_tool)), 1),
                "heaviest_tools": dict(heaviest),
            },
        )
    )
    print(
        f"\n[capability] manifest_context_headroom = {score.pct}%  "
        f"({manifest} tokens of manifest for {len(per_tool)} tools, "
        f"mean {score.detail['mean_tokens_per_tool']}/tool)"
    )
    print(f"             heaviest: {dict(heaviest)}")

    assert manifest < REFERENCE_CONTEXT, (
        f"the tool manifest ({manifest} tokens) no longer fits the {REFERENCE_CONTEXT}-token "
        "reference window at all — a small model cannot use this skill"
    )


def test_per_tool_token_discipline(board, tools):
    """Share of tools whose individual manifest cost stays under the ceiling.

    Tracked separately from the total because the two regress for different
    reasons and want different fixes: a falling total is usually "we added
    tools" (merge or gate them), a falling share here is always "one description
    grew a manual inside it" (move it to references/).
    """
    per_tool = {t.name: _tool_tokens(t) for t in tools}
    within = {n: v for n, v in per_tool.items() if v <= PER_TOOL_CEILING}
    over = {n: v for n, v in sorted(per_tool.items(), key=lambda kv: -kv[1]) if v > PER_TOOL_CEILING}

    score = board.add(
        Score(
            name="per_tool_token_discipline",
            value=len(within),
            maximum=len(per_tool),
            unit="tools",
            detail={"ceiling": PER_TOOL_CEILING, "over_ceiling": over},
        )
    )
    print(f"\n[capability] per_tool_token_discipline = {score.pct}%  (over ceiling: {over})")

    assert score.pct >= 50.0, f"most tools now exceed {PER_TOOL_CEILING} manifest tokens: {over}"

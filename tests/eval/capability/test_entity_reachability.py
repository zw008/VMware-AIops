"""Capability — can the model obtain the names the tools demand?

What this measures
------------------
Many tools require an exact entity name: ``vm_name``, ``host_name``,
``datastore_name``, ``cluster_name``. This eval asks, for every such required
parameter, whether the model has any way to *get* that name — either from
another tool on the same surface, or from a description that names the specific
producer to call. A parameter with neither is a **broken chain**: a tool the
model can see, wants to use, and cannot correctly invoke.

It scores the full surface and the ``VMWARE_READ_ONLY=true`` surface separately,
because gating removes tools and can turn a working chain into a broken one.

Why it matters for a small model
--------------------------------
This is the failure the whole family's structured-output work was aimed at,
approached from the input side rather than the output side. A large model that
needs a VM name and has no listing tool will say so, or reach for a companion
skill, or ask the user. A small model does the thing that looks locally
plausible: it invents a name that matches the user's phrasing — ``"the web
server"`` becomes ``vm_name="web-server"`` — gets a not-found error, and reports
that the VM does not exist. The user is then told a false fact about their
infrastructure, which is strictly worse than an error.

Guessing an identifier is the single highest-consequence hallucination on this
surface, and it is invited by exactly one thing: a required name with no
reachable producer.

What counts as reachable
------------------------
``producer_on_surface`` — another tool on the same surface is an *entry point*
    (needs no entity name itself) and enumerates that entity type. This is the
    strong form: the model can chain without leaving the skill.
``routed_in_description`` — the description names a concrete producer: a
    specific sibling tool, or a companion skill that owns that inventory. This
    is the weaker but legitimate form. A skill that deliberately delegates
    inventory to a sibling is not broken *provided it says so*, because
    "call vmware-monitor's list_virtual_machines first" is an instruction a weak
    model can follow. "Exact VM name as shown in vCenter inventory" is not — it
    describes where the name exists in the world, not how to obtain it.

How to read the score
---------------------
Percentage of required entity-name parameters that are reachable by either
route. **100%** every demanded name is obtainable; **80–99%** a few tools invite
a guess; **<80%** identifier hallucination should be expected in normal use. The
``broken_chains`` detail lists the exact parameters to fix, and the cheapest fix
is almost always one sentence in a description rather than a new tool.

Compare the two scores against each other: a large drop under read-only mode
means the safety gate is buying its safety by making the surface unusable, which
is worth knowing before recommending it as a default.
"""

from __future__ import annotations

import pytest

from ._scoring import Score
from ._skill import COMPANION_SKILLS, ENTITY_WORDS
from ._skill import NOT_AN_ENTITY as SKILL_NOT_AN_ENTITY

pytestmark = pytest.mark.capability

#: Parameter names that denote an entity a model must have discovered somewhere.
#: ``target`` is excluded: it comes from the operator's own config.yaml, not from
#: an API listing, and every description already points at config.
#: Plural forms are included because a list-valued identifier parameter
#: (``metric_keys``, ``symptom_definition_ids``) is the same lookup as its
#: singular; omitting them dropped those parameters from scoring entirely.
ENTITY_SUFFIXES = ("_name", "_id", "_uuid", "_key", "_ids", "_keys", "_names")

#: Exclusions true for every skill: these end in an entity suffix but are not
#: things a model discovers from an API. ``target`` comes from the operator's own
#: config.yaml; the rest are paths, filters and free text.
GENERIC_NOT_AN_ENTITY = frozenset(
    {
        "target",
        "user_name",
        "username",
        "file_name",
        "local_path",
        "remote_path",
        "pattern",
        "path",
        "sort_by",
        "fields",
    }
)

NOT_AN_ENTITY = GENERIC_NOT_AN_ENTITY | SKILL_NOT_AN_ENTITY

#: Verbs marking a tool that *creates* the thing its parameter names. The name of
#: an object being created is chosen by the user, not discovered from an API, so
#: it is not a lookup and must not be scored as an unreachable one.
CREATION_VERBS = ("create", "deploy", "provision", "register", "add")


def _names_a_new_object(param: str, tool_name: str, entity: str) -> bool:
    """True when ``param`` names the object ``tool_name`` is about to create.

    Requires both a creation verb *and* the entity appearing in the tool's own
    name, so ``vm_create_snapshot(snapshot_name=...)`` reads as invented while
    ``batch_linked_clone_vms(snapshot_name=...)`` — which clones *from* an
    existing snapshot — correctly stays a lookup.
    """
    low = tool_name.lower()
    if not any(v in low for v in CREATION_VERBS):
        return False
    return any(w in low for w in ENTITY_WORDS.get(entity, (entity,)))


def _match(stem: str) -> str | None:
    for entity, words in ENTITY_WORDS.items():
        if stem in words or stem == entity:
            return entity
    return None


def _entity_of(param: str, tool_name: str) -> str | None:
    """Map a parameter name to an entity token, or None if it is not an entity.

    Three shapes, because the family does not share one naming convention:

    ``vm_name`` / ``segment_id``  — suffix stripped, stem matched.
    ``namespace`` / ``pool``      — no suffix at all. Matched whole, so a skill
        whose identifiers are bare nouns is scored rather than skipped. These are
        opt-in through ``ENTITY_WORDS``; the coverage figure in the score detail
        is what shows when one has been missed.
    ``name``                      — takes its entity from the tool's own subject.
        Every token is tried, not just the first: vmware-aiops names tools
        subject-first (``cluster_info``) while vmware-vks names them verb-first
        (``get_namespace``), and reading only the first token resolves the latter
        to the verb and quietly drops the parameter.
    """
    low = param.lower()
    if low in NOT_AN_ENTITY:
        return None

    for suffix in ENTITY_SUFFIXES:
        if low.endswith(suffix):
            return _match(low[: -len(suffix)])

    if low != "name":
        return _match(low)

    for token in tool_name.lower().split("_"):
        entity = _match(token)
        if entity:
            return entity
    return None


def _required_entity_params(tool) -> list[tuple[str, str]]:
    schema = tool.inputSchema or {}
    required = schema.get("required", []) or []
    out = []
    for param in required:
        entity = _entity_of(param, tool.name)
        if entity and not _names_a_new_object(param, tool.name, entity):
            out.append((param, entity))
    return out


def _entry_points(tools) -> tuple:
    """Tools callable with no entity name in hand — the only possible chain starts."""
    return tuple(t for t in tools if not _required_entity_params(t))


def _enumerated_entities(tool) -> tuple[str, ...]:
    """Entity tokens this tool plausibly enumerates, judged from its name."""
    name = tool.name.lower()
    keywords = ("list", "scan", "browse", "summary", "attention", "info", "available", "members")
    if not any(k in name for k in keywords):
        return ()
    return tuple(e for e, words in ENTITY_WORDS.items() if any(w in name for w in words))


def _producers(tools) -> dict[str, list[str]]:
    """Entity token -> tools that enumerate it and are themselves reachable.

    Computed to a fixpoint rather than restricted to entry points, because a
    producer may legitimately need an input of its own: ``vm_list_snapshots``
    requires a ``vm_name``, but once some tool supplies VM names it becomes a
    perfectly good source of snapshot names. Requiring producers to be entry
    points would report those second-hop chains as broken when a model can in
    fact walk them.
    """
    found: dict[str, list[str]] = {}
    reachable_entities: set[str] = set()

    for _ in range(len(tools) + 1):
        grew = False
        for tool in tools:
            needed = {e for _p, e in _required_entity_params(tool)}
            if not needed <= reachable_entities:
                continue
            for entity in _enumerated_entities(tool):
                if tool.name not in found.setdefault(entity, []):
                    found[entity].append(tool.name)
                    grew = True
                if entity not in reachable_entities:
                    reachable_entities.add(entity)
                    grew = True
        if not grew:
            break
    return {e: names for e, names in found.items() if names}


def _all_required(tools) -> int:
    """Count of every required parameter, entity-shaped or not."""
    return sum(len((t.inputSchema or {}).get("required", []) or []) for t in tools)


def _assess(tools) -> tuple[list[dict], list[dict]]:
    """Return ``(reachable, broken)`` records for every required entity param."""
    producers = _producers(tools)
    names = {t.name for t in tools}
    reachable: list[dict] = []
    broken: list[dict] = []

    for tool in tools:
        desc = tool.description or ""
        for param, entity in _required_entity_params(tool):
            on_surface = producers.get(entity, [])
            routed = [n for n in names - {tool.name} if n in desc]
            companion = [s for s in COMPANION_SKILLS if s in desc]
            record = {
                "tool": tool.name,
                "param": param,
                "entity": entity,
                "producer_on_surface": on_surface,
                "routed_in_description": routed[:3],
                "companion_skill_named": companion,
            }
            if on_surface or routed or companion:
                reachable.append(record)
            else:
                broken.append(record)
    return reachable, broken


def _record(board, tools, label: str) -> Score:
    reachable, broken = _assess(tools)
    total = len(reachable) + len(broken)
    strong = sum(1 for r in reachable if r["producer_on_surface"])
    # A surface with no identifier parameters at all (vmware-debug has two tools
    # and neither takes one) is navigable, not broken. Scoring it 0/1 would read
    # as the worst possible result for the best possible case. The callers assert
    # that the vocabulary is genuinely empty before trusting this branch, so it
    # cannot be reached by a vocabulary that simply failed to match.
    score = board.add(
        Score(
            name=f"entity_reachability_{label}",
            value=len(reachable) if total else 1,
            maximum=max(1, total),
            unit="required entity params",
            detail={
                "tool_count": len(tools),
                "required_entity_params": total,
                # Coverage sits beside the score on purpose. A parameter the
                # vocabulary does not recognise is not scored as unreachable, it
                # is not scored at all — so the percentage above is only as
                # meaningful as the fraction of the surface it was computed over.
                "required_params_classified": f"{total}/{_all_required(tools)}",
                "reachable_on_surface": strong,
                "reachable_only_via_description": len(reachable) - strong,
                "broken_chains": broken,
                "entry_points": [t.name for t in _entry_points(tools)],
            },
        )
    )
    print(
        f"\n[capability] entity_reachability_{label} = {score.pct}%  "
        f"({len(reachable)}/{total} required names obtainable; "
        f"{strong} from this surface, {len(reachable) - strong} via documented routing)"
    )
    if broken:
        print(f"             BROKEN CHAINS: {[(b['tool'], b['param']) for b in broken]}")
    return score


def _assert_vocabulary_fits(score) -> bool:
    """True when there is something to score; raises when the map does not fit.

    Zero matched parameters has two very different causes. A skill can genuinely
    have no discoverable identifiers. Or the vocabulary can be the wrong one —
    the state a fresh port is in before anyone writes ``ENTITY_WORDS``, and the
    state in which every number this file prints is computed over an empty set.
    Telling them apart is exactly what the declaration is for: an empty map says
    "no identifiers here" out loud, so a populated map that matches nothing is
    a defect rather than a valid answer.
    """
    if score.detail["required_entity_params"]:
        return True
    assert not ENTITY_WORDS, (
        "no required parameter matched the entity vocabulary, yet _skill.py "
        "declares one — the map does not fit this surface, so every score in "
        "this file was computed over an empty set. Fix ENTITY_WORDS, or empty "
        "it to declare that this skill has no discoverable identifiers."
    )
    return False


def test_entity_reachability_full_surface(board, tools):
    """Every required entity name must be obtainable on the ungated surface."""
    score = _record(board, tools, "full")
    if not _assert_vocabulary_fits(score):
        return
    assert score.pct >= 50.0, (
        f"only {score.pct}% of required entity names are obtainable — a model "
        "driving this skill has to invent identifiers, and invented identifiers "
        "produce confident false statements about the operator's infrastructure"
    )


def test_entity_reachability_read_only_surface(board, gated_tools):
    """The same question after the read-only gate has removed tools.

    Recorded separately because a safety control that leaves the remaining tools
    uncallable has traded one failure mode for a worse one.
    """
    score = _record(board, gated_tools, "read_only")
    if not _assert_vocabulary_fits(score):
        return
    assert score.pct >= 50.0, (
        f"read-only mode drops entity reachability to {score.pct}% — the gate is "
        "making the surface unusable rather than merely safe"
    )


def test_every_surface_has_an_entry_point(board, tools, gated_tools):
    """At least one tool must be callable with nothing in hand, in both modes.

    The degenerate broken surface: if every tool demands a name, there is no
    first call to make and the skill is unreachable regardless of model size.
    """
    full_entries = _entry_points(tools)
    gated_entries = _entry_points(gated_tools)
    board.add(
        Score(
            name="entry_point_availability",
            value=min(len(full_entries), len(gated_entries)),
            maximum=max(1, len(gated_tools)),
            unit="entry points",
            detail={
                "full_entry_points": len(full_entries),
                "read_only_entry_points": len(gated_entries),
            },
        )
    )
    print(
        f"\n[capability] entry points: {len(full_entries)} full / "
        f"{len(gated_entries)} read-only"
    )
    assert full_entries, "no tool can be called without an entity name already in hand"
    assert gated_entries, "read-only mode left no callable entry point"


def test_entity_vocabulary_covers_the_surface(tools):
    """The vocabulary in ``_skill.py`` must classify every entity-shaped parameter.

    Without this the suite degrades silently rather than loudly. An unrecognised
    parameter is not counted as unreachable — it is not counted at all, so a
    skill whose entities are missing from ``ENTITY_WORDS`` scores on the handful
    it happens to recognise and reports that as the state of the whole surface.
    A vSphere vocabulary applied to vmware-nsx would classify one stray
    ``cluster_name``, miss twenty segment and gateway names, and print a
    confident number derived from 5% of the tools.

    Total non-coverage already fails (nothing recognised scores 0%). Partial
    coverage is the dangerous case, and it is the normal case when this suite is
    copied to a new skill. So: anything ending in an entity suffix must either
    map to an entity token or be named as a deliberate exclusion.
    """
    unclassified: dict[str, list[str]] = {}
    for tool in tools:
        for param in (tool.inputSchema or {}).get("required", []) or []:
            low = param.lower()
            if low in NOT_AN_ENTITY or _entity_of(param, tool.name):
                continue
            if low == "name" or low.endswith(ENTITY_SUFFIXES):
                unclassified.setdefault(param, []).append(tool.name)

    assert not unclassified, (
        "these required parameters look like entities but the vocabulary does not "
        f"classify them: {unclassified}. Add each stem to ENTITY_WORDS in _skill.py "
        "(so reachability is scored for it), or to NOT_AN_ENTITY (if the operator "
        "supplies it rather than discovering it). Leaving them unclassified makes "
        "every score in this file cover less of the surface than it claims to."
    )

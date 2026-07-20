"""Capability — when a call fails, is the model told enough to fix it?

What this measures
------------------
CLAUDE.md mandates "教学性错误" (teaching errors): an error must not merely
report a failure, it must carry the correction. This eval extracts every error
message the package can raise — by parsing the AST, so it sees messages no test
happens to trigger — and scores each on three dimensions. It also checks the
live MCP error payload shape.

Why it matters for a small model
--------------------------------
Error recovery is where the capability gap between a large and a small model is
widest. Given ``VM 'web-99' not found``, a large model recovers on its own: it
infers that names come from an inventory call, finds one in the tool list, calls
it, and retries with a corrected name. A small model does none of that. It
either surfaces the raw error to the user as a dead end, or — the failure mode
issue #31 actually reported — smooths it over into a confident, wrong summary.

The difference between those two outcomes is entirely in the message text.
``VM 'web-99' not found. Run vmware-monitor's list_virtual_machines (filter by
name, e.g. 'web-99*') to see available VMs and copy an exact name.`` converts
recovery from an inference
problem into an instruction-following problem, which is precisely the thing weak
models remain good at. Every point scored here moves one more failure across
that line.

The three dimensions
--------------------
``names_input``    — the message interpolates the offending value, or states the
                     valid range/set it violated. Without this the model cannot
                     tell which of several arguments was wrong.
``states_remedy``  — an actionable instruction ("run", "check", "set", "copy an
                     exact name"), not just a diagnosis.
``names_artifact`` — names the specific tool, CLI command, env var, or file to
                     act on. This is what makes the remedy executable rather
                     than aspirational; a model told to "verify connectivity"
                     without being told *how* will invent a command. Tool names
                     are matched against the live registry, so pointing at a
                     tool that does not exist scores zero — a remedy the model
                     cannot carry out is not a remedy. Naming a companion
                     skill's CLI does count: a documented hand-off is followable.

How to read the score
---------------------
A 0–100 index over all raise sites × three dimensions. **>70** most failures are
self-correcting for a weak model; **50–70** the common paths teach and the long
tail does not; **<50** errors are mostly dead ends. ``names_input`` is usually
near-saturated because f-strings make it nearly free — the signal lives in
``states_remedy`` and ``names_artifact``, so read those per-dimension figures
before the aggregate.

The ``dead_end_errors`` list in the detail block is the actionable output of this
whole file: those are the exact messages to rewrite next, in priority order.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
from collections.abc import Callable

import pytest

from ._scoring import Score
from ._skill import CLI_NAME, COMPANION_SKILLS, PACKAGE, SERVER_MODULE

pytestmark = pytest.mark.capability

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[3] / PACKAGE

#: Imperative recovery language. Deliberately verb-led: "not found" is a
#: diagnosis, "run list_virtual_machines" is a remedy, and only the second helps.
REMEDY_MARKERS = (
    "run ",
    "check ",
    "set ",
    "use ",
    "copy ",
    "edit ",
    "verify ",
    "try ",
    "see ",
    "install ",
    "configure ",
    "add ",
    "remove ",
    "retry",
    "re-run",
    "rerun",
    "must be",
    "expected ",
    "did you mean",
    "available:",
    "supported:",
    "choose ",
    "pick ",
    "specify ",
    "provide ",
    "pass ",
    "ensure ",
)

#: Actionable things that are not tool names: this skill's CLI, a sibling skill
#: to route to, a config file, an env var, a flag.
#:
#: Companion skills belong here for the same reason they count in
#: ``test_entity_reachability``: "run 'vmware-storage iscsi status <host>'" is a
#: documented hand-off, and a model can follow it. Scoring it as a dead end
#: because the named CLI is not *this* package's understated the family's
#: cross-skill errors by ~14 points in vmware-aiops alone.
STATIC_ARTIFACT_MARKERS = (
    CLI_NAME,
    "config.yaml",
    "config.example.yaml",
    ".env",
    "_mcp",
    "environment variable",
)

#: Companion CLI names, matched so that one cannot swallow another. Plain
#: substring matching credited ``vmware-nsx`` inside ``vmware-nsx-security``, so
#: that skill scored a documented hand-off for every mention of *itself* — and
#: its own CLI citations were never checked against its own command tree.
#: The lookahead is what keeps a prefix from claiming a longer name.
COMPANION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in sorted(COMPANION_SKILLS, key=len, reverse=True))
    + r")(?![\w-])"
)

#: A real long flag, not any pair of hyphens. ``"--"`` used to be a static
#: marker, which credited every em-dash-adjacent construction and every ``--``
#: appearing for any reason — two skills reported banking ``names_artifact`` on
#: it without naming a flag at all. Requiring a flag-shaped token is the whole
#: fix; it costs nothing on messages that really do cite ``--target``.
FLAG_PATTERN = re.compile(r"--[a-z][a-z0-9-]{2,}")

#: Env var references: ``VMWARE_FOO_PASSWORD``. Previously only reachable via
#: the prose phrase "environment variable", so a message naming the variable
#: precisely — the more useful form — scored lower than one describing it
#: vaguely.
ENV_VAR_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){2,}\b")


def _cli_commands() -> frozenset[str] | None:
    """Every runnable command *path* the CLI registers, or None if unresolvable.

    Tool names are checked against the live registry, but CLI invocations were
    taken on faith — and one skill shipped thirteen error hints telling the model
    to run ``<cli> doctor``, a command that does not exist (it is ``check``).
    The rubric scored every one of them full marks, so the fix and the phantom
    were worth exactly the same. A cited command is an artifact only if it can be
    run.

    Full paths, not just first tokens. Checking only the first token accepted
    ``<cli> pool list`` because ``pool`` is a real *group* — while ``pool list``
    does not exist. An agent writing that message caught itself by hand; the
    check did not, which made this function's own name a promise it was not
    keeping.

    Walked through click rather than Typer's registration lists, because that is
    the tree the user's shell actually dispatches against.

    Returns None rather than an empty set when the app cannot be located, so the
    caller can report the check as unavailable instead of silently refuting every
    CLI reference — an unverifiable claim is not a refuted one.
    """
    import click
    import typer

    for dotted, attr in ((f"{PACKAGE}.cli", "app"), (f"{PACKAGE}.cli._root", "app")):
        try:
            app = getattr(importlib.import_module(dotted), attr, None)
        except Exception:  # noqa: BLE001 — absence is the answer, not an error
            continue
        if app is None:
            continue
        try:
            root = typer.main.get_command(app)
        except Exception:  # noqa: BLE001
            continue
        paths: set[str] = set()

        def walk(cmd, prefix: list[str]) -> None:
            if isinstance(cmd, click.Group):
                for name, sub in cmd.commands.items():
                    walk(sub, [*prefix, name])
            elif prefix:
                paths.add(" ".join(prefix))

        walk(root, [])
        if paths:
            return frozenset(paths)
    return None


_UNSET = object()


def _artifact_matcher(tools, cli_commands=_UNSET) -> Callable[[str], bool]:
    """Predicate: does this text name something the operator can actually act on?

    Static markers plus the tool names the registry actually exposes. This
    replaces the earlier ``list_`` / ``get_`` prefix heuristic, which was wrong
    in both directions. It missed every tool not named that way —
    ``cluster_info``, ``browse_datastore``, ``vm_info`` all read as "names
    nothing concrete" while naming a real tool. And it credited *any*
    plausible-looking name, including tools that do not exist: vmware-monitor
    shipped an error telling the model to run ``list_vms``, a tool with no such
    name on the surface, and this rubric scored it full marks. A remedy pointing
    at a phantom tool is worse than no remedy, so the marker set is now the live
    registry — the same source of truth ``family_smoke.sh`` checks error
    messages against.

    Tool names match on word boundaries rather than as substrings. Plain
    ``in`` would credit ``cluster_infos`` because ``cluster_info`` is a prefix
    of it, which reintroduces the phantom-tool hole this function exists to
    close — the same defect wearing a different name. Static markers stay
    substring-matched: ``--``, ``.env`` and ``config.yaml`` have no word
    boundaries to speak of.

    Tool names are restricted to those containing ``_``, the family's mandated
    ``<domain>_<action>_<resource>`` form (CLAUDE.md, MCP tool design). A bare
    word would match incidental prose rather than a deliberate reference.
    """
    names = sorted({t.name.lower() for t in tools if "_" in t.name})
    pattern = (
        re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b") if names else None
    )
    commands = _cli_commands() if cli_commands is _UNSET else cli_commands
    #: An *invocation* — quoted, backticked, or introduced by a run-ish verb —
    #: claims a specific subcommand and can therefore be wrong. A passing
    #: mention ("install vmware-monitor") only names the executable and claims
    #: nothing to verify, so it is credited as-is.
    #: The captured token deliberately admits ``_`` so that "vmware-monitor
    #: get_alarms" is seen whole. Family CLI subcommands are kebab-case and MCP
    #: tools are snake_case, so a token containing ``_`` is a tool reference,
    #: not a subcommand claim — it is checked against the registry below rather
    #: than being mistaken for a phantom command named "get".
    cli_call = re.compile(
        r"(?:['\"`]|\b(?:run|re-run|rerun|via|using|with)\s+['\"`]?)"
        + re.escape(CLI_NAME.lower())
        + r"((?:\s+[a-z][a-z0-9_-]*){1,3})"
    )
    cli_mention = re.compile(re.escape(CLI_NAME.lower()))

    def _valid(tokens: list[str]) -> bool:
        """True if some prefix of the cited tokens is a runnable command path.

        A prefix, because real messages trail prose — "run 'vmware-nsx init' to
        rebuild it" cites `init` followed by words that are not arguments. A
        *group* on its own is not a prefix that runs, so `pool` alone never
        satisfies this even though `pool members` does.
        """
        return any(" ".join(tokens[: i + 1]) in commands for i in range(len(tokens)))

    def _cites_this_cli(low: str) -> bool:
        if not cli_mention.search(low):
            return False
        claims = [
            [t for t in m.group(1).split() if "_" not in t] for m in cli_call.finditer(low)
        ]
        claims = [c for c in claims if c]
        if not claims:
            return True  # names the executable, or a tool the registry check reads
        if commands is None:
            return True  # app not introspectable: unverifiable, not refuted
        return any(_valid(c) for c in claims)

    def names_artifact(text: str) -> bool:
        low = text.lower()
        if any(m in low for m in STATIC_ARTIFACT_MARKERS if m != CLI_NAME):
            return True
        # A companion hand-off counts, but not when the "companion" is this
        # skill's own name wearing a shorter prefix.
        if any(m.group(0) != CLI_NAME.lower() for m in COMPANION_PATTERN.finditer(low)):
            return True
        if _cites_this_cli(low):
            return True
        if FLAG_PATTERN.search(low) or ENV_VAR_PATTERN.search(text):
            return True
        return bool(pattern and pattern.search(low))

    return names_artifact


def _file_symbols(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """Module-level string constants, and the strings each function can return.

    Both are needed to read a message the way the agent receives it rather than
    the way it appears at the raise site.
    """
    consts: dict[str, str] = {}
    returns: dict[str, str] = {}
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            if isinstance(stmt.value.value, str):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        consts[tgt.id] = stmt.value.value
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts = [
                n.value.value
                for n in ast.walk(stmt)
                if isinstance(n, ast.Return)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)
            ]
            parts += [
                "".join(v.value for v in n.value.values if isinstance(v, ast.Constant))
                for n in ast.walk(stmt)
                if isinstance(n, ast.Return) and isinstance(n.value, ast.JoinedStr)
            ]
            if parts:
                returns[stmt.name] = " ".join(parts)
    return consts, returns


def _iter_raise_messages():
    """Yield ``(file, lineno, message, interpolates, composed)`` per literal raise.

    Holes are no longer blanked out. Rendering every f-string hole as ``{}`` made
    the rubric blind to any guidance the code composes at runtime — a hint
    hoisted into a module constant, or produced by a ``_hint_for_status()``
    helper, scored as though the message named nothing. Four skills independently
    reported the same consequence: the *better* engineering pattern measured as
    the worse one, and rewriting a shared hint as a duplicated inline literal
    would have raised the score without helping anyone.

    So a hole is resolved when it can be: a name bound to a module-level string,
    or a call to a function in the same file, whose returnable strings are all
    folded in. ``composed`` marks the second case, because folding in every
    branch is an approximation — the message credits an artifact that only some
    branches name. Reporting the count keeps that visible instead of burying it
    in the aggregate.
    """
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - unreadable source
            continue
        yield from _messages_in_tree(tree, path.name)


def _messages_in_tree(tree: ast.AST, filename: str):
    """The per-file half of ``_iter_raise_messages``, split out to be testable.

    Kept separate so the regression suite can feed it a source string and pin
    the resolution rules directly, instead of only observing them through
    whatever the package happens to contain today.
    """
    consts, returns = _file_symbols(tree)

    def _hole(node) -> tuple[str, bool]:
        expr = node.value
        if isinstance(expr, ast.Name) and expr.id in consts:
            return consts[expr.id], False
        if isinstance(expr, ast.Call):
            fn = expr.func
            fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if fname in returns:
                return returns[fname], True
        return "{}", False

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        if not node.exc.args:
            continue
        arg = node.exc.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            yield (filename, node.lineno, arg.value, False, False)
        elif isinstance(arg, ast.JoinedStr):
            parts, composed = [], False
            for v in arg.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                else:
                    rendered, approx = _hole(v)
                    parts.append(rendered)
                    composed = composed or approx
            holes = any(isinstance(v, ast.FormattedValue) for v in arg.values)
            yield (filename, node.lineno, "".join(parts), holes, composed)


def _grade(text: str, interpolates: bool, names_artifact: Callable[[str], bool]) -> dict[str, bool]:
    low = text.lower()
    states_range = any(k in low for k in ("must be", "available:", "supported:", "expected "))
    return {
        "names_input": interpolates or states_range,
        "states_remedy": any(m in low for m in REMEDY_MARKERS),
        "names_artifact": names_artifact(text),
    }


@pytest.fixture(scope="session")
def names_artifact(tools) -> Callable[[str], bool]:
    """Built once per run, from the registry rather than from a guess."""
    return _artifact_matcher(tools)


@pytest.fixture(scope="session")
def graded_errors(names_artifact):
    return tuple(
        (f, ln, text, composed, _grade(text, holes, names_artifact))
        for f, ln, text, holes, composed in _iter_raise_messages()
    )


def test_error_actionability_index(board, graded_errors):
    """Record the aggregate index and name the dead ends worth rewriting."""
    assert graded_errors, "found no raise sites to score — has the package layout moved?"

    dims = ("names_input", "states_remedy", "names_artifact")
    earned = sum(sum(g.values()) for *_r, g in graded_errors)
    possible = len(graded_errors) * len(dims)
    per_dimension = {
        d: round(100.0 * sum(g[d] for *_r, g in graded_errors) / len(graded_errors), 1)
        for d in dims
    }

    dead_ends = [
        {"where": f"{f}:{ln}", "message": text[:100], "missing": sorted(k for k, v in g.items() if not v)}
        for f, ln, text, _c, g in graded_errors
        if not g["states_remedy"] and not g["names_artifact"]
    ]
    composed = [f"{f}:{ln}" for f, ln, _t, c, _g in graded_errors if c]

    score = board.add(
        Score(
            name="error_actionability",
            value=earned,
            maximum=possible,
            detail={
                "raise_sites": len(graded_errors),
                "per_dimension_pct": per_dimension,
                "dead_end_count": len(dead_ends),
                "dead_end_errors": dead_ends[:15],
                # Sites whose guidance is assembled at runtime. Scored by folding
                # in every branch the helper can return, so the credit is an
                # upper bound: some branches may name nothing. Listed so the
                # approximation stays visible rather than dissolving into the
                # aggregate.
                "composed_hint_sites": composed,
            },
        )
    )
    print(f"\n[capability] error_actionability = {score.pct}%  ({earned}/{possible})")
    print(f"             per-dimension: {per_dimension}")
    print(f"             dead ends (no remedy, no artifact): {len(dead_ends)}/{len(graded_errors)}")

    assert score.pct >= 35.0, (
        f"error messages collapsed to {score.pct}% actionable — failures are now dead "
        f"ends for a model that cannot infer recovery. Worst: {dead_ends[:5]}"
    )


def test_teaching_error_rate(board, graded_errors):
    """Share of errors carrying *both* a remedy and something concrete to act on.

    Stricter than the aggregate and closer to what CLAUDE.md actually mandates:
    an error that names the bad value but not the fix still leaves a weak model
    stuck. This is the number to move.
    """
    teaching = [g for *_r, g in graded_errors if g["states_remedy"] and g["names_artifact"]]
    score = board.add(
        Score(
            name="teaching_error_rate",
            value=len(teaching),
            maximum=len(graded_errors),
            unit="messages",
        )
    )
    print(f"\n[capability] teaching_error_rate = {score.pct}%  ({len(teaching)}/{len(graded_errors)})")
    assert score.pct >= 15.0, "almost no error message tells the model how to recover"


def _truncation_budget() -> int | None:
    """The character cap ``_safe_error`` applies, read from the server source.

    Read rather than assumed because the family does not agree on one number —
    vmware-harden deliberately uses a wider bound because its messages carry two
    absolute paths before the remedy. Hardcoding 300 here would have quietly
    passed that repo while failing to describe it.
    """
    module = importlib.import_module(SERVER_MODULE)
    caps = []
    for source in sorted(pathlib.Path(module.__file__).parent.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        for m in re.finditer(
            r"sanitize\(\s*(?:str\()?\s*exc\)?\s*,\s*(\d+)\s*\)",
            source.read_text(encoding="utf-8", errors="replace"),
        ):
            caps.append(int(m.group(1)))
    return min(caps) if caps else None


def test_truncation_budget_matches_what_the_server_really_applies():
    """Cross-check the parsed cap against the wrapper's actual behaviour.

    ``_truncation_budget`` reads a number out of the source, and a number read
    out of source is a claim about behaviour, not behaviour. If it drifted — or
    if the regex matched the wrong call — every finding built on it would be
    wrong in the safe-looking direction, reporting "nothing is truncated"
    because the yardstick grew.
    """
    budget = _truncation_budget()
    if budget is None:
        pytest.skip("no sanitize() cap found in the MCP server")

    module = importlib.import_module(SERVER_MODULE)
    safe_error = getattr(module, "_safe_error", None)
    if safe_error is None:  # skills that wrap errors elsewhere
        for name in ("_shared", "server"):
            helper = importlib.import_module(f"{module.__package__}.{name}", package=None)
            safe_error = getattr(helper, "_safe_error", None)
            if safe_error:
                break
    if safe_error is None:
        pytest.skip("no _safe_error to cross-check against")

    produced = len(safe_error(ValueError("x" * (budget * 3)), "probe"))
    assert produced == budget, (
        f"the cap parsed from source ({budget}) is not the cap applied at runtime "
        f"({produced}) — every truncation finding is measured against the wrong bound"
    )


def _truncation_findings(graded, budget: int):
    """Split scored messages into ones already cut and ones a long value can cut.

    Pure, and separate from the test, so the regression suite can exercise it on
    fabricated messages. Driven only by whatever the package contains today it
    would sit at 100% and verify nothing — passing for the same reason an empty
    check passes.
    """
    over, at_risk = [], []
    for f, ln, text, composed, g in graded:
        if not (g["states_remedy"] or g["names_artifact"]):
            continue  # no remedy to preserve
        # A composed message's text is every branch of its hint helper folded
        # together — useful for asking "can this ever name a tool", useless as a
        # length. Measuring it against the cap invented a 759-character message
        # that is never produced at runtime, which is the same overclaim this
        # check exists to catch, committed by the check itself.
        if not composed and len(text) > budget:
            over.append({"where": f"{f}:{ln}", "chars": len(text), "budget": budget})
        low = text.lower()
        hole = text.rfind("{}")
        last_remedy = max((low.rfind(m) for m in REMEDY_MARKERS if m in low), default=-1)
        if hole >= 0 and last_remedy > hole:
            at_risk.append(f"{f}:{ln}")
    return over, at_risk


def test_remedies_survive_the_truncation_cap(board, graded_errors):
    """The rubric reads the source; the agent reads what survives ``sanitize``.

    Every scored message above is graded on its full text, but ``_safe_error``
    caps what actually reaches the agent — with no ellipsis, so a cut is
    invisible. One skill was found shipping a 396-character message whose
    closing remedy ("re-run ``<cli> init``") had never once been delivered,
    while this file scored it a perfectly taught error. That is the failure this
    whole suite exists to catch, occurring inside the suite's own blind spot.

    Two ways a remedy is lost, reported separately because only one is certain:

    ``over_budget``      the static text alone exceeds the cap — cut today.
    ``remedy_after_hole`` the remedy trails an interpolation, so however short
                          the template looks, a long value can push the remedy
                          past the cut at runtime. Reported, not asserted: it is
                          a hazard, and whether it fires depends on real data.
    """
    budget = _truncation_budget()
    if budget is None:
        pytest.skip("no sanitize() cap found in the MCP server — nothing to measure")

    over, at_risk = _truncation_findings(graded_errors, budget)
    scored = [1 for _f, _l, _t, _c, g in graded_errors if g["states_remedy"] or g["names_artifact"]]
    score = board.add(
        Score(
            name="remedy_survives_truncation",
            value=len(scored) - len(over),
            maximum=len(scored) or 1,
            unit="messages",
            detail={
                "budget_chars": budget,
                "over_budget": over[:10],
                "remedy_after_interpolation": at_risk[:10],
            },
        )
    )
    print(f"\n[capability] remedy_survives_truncation = {score.pct}%  (cap {budget} chars)")
    if at_risk:
        print(f"             remedy trails an interpolation at: {at_risk[:5]}")

    assert not over, (
        f"{len(over)} message(s) are longer than the {budget}-char cap, so the "
        f"remedy is cut before the agent sees it — and every rubric above still "
        f"scores them as taught: {over[:5]}"
    )


def _error_returns_in_server():
    """Yield ``(lineno, is_dict, has_hint, hint_text)`` for each caught-error return.

    Scanned statically out of the MCP server module rather than by calling a
    wrapper, because the family does not agree on one: this skill may use a
    decorator, a shared helper, or a hand-written ``try/except`` inside every
    tool. The static form covers all three, and covers the hand-written case
    *exhaustively* — which is the one that drifts, since each site is written
    independently and nothing forces them to match.
    """
    module = importlib.import_module(SERVER_MODULE)
    server_dir = pathlib.Path(module.__file__).parent

    def _resolve(node) -> str:
        """Render a hint expression as text, following module-level constants.

        Hoisting a shared hint into a constant (``_DOCTOR_HINT``) is the better
        pattern than repeating a literal at every call site, so the scan must
        follow the reference — otherwise the rubric would quietly reward
        copy-paste over the cleaner form.
        """
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.JoinedStr):
            # Resolve interpolations too, not just the literal segments. The
            # first version joined only Constant parts, so
            # `f"Error: {msg} {_DOCTOR_HINT}"` rendered as "Error:  " and the
            # hint vanished — scoring a centralised, hint-carrying wrapper as
            # though it returned a bare string. An eval that misreads the
            # better pattern as the worse one is worse than no eval.
            parts = []
            for piece in node.values:
                if isinstance(piece, ast.Constant):
                    parts.append(str(piece.value))
                elif isinstance(piece, ast.FormattedValue):
                    parts.append(_resolve(piece.value))
            return "".join(parts)
        if isinstance(node, ast.Name):
            # Resolve against the module the *source file* belongs to, not the
            # server module. A hint hoisted into `_DOCTOR_HINT` in a helper file
            # returned "" when looked up on `server`, scoring a hint-carrying
            # payload as having none.
            if node.id in file_constants:
                return file_constants[node.id]
            return str(getattr(module, node.id, ""))
        return ""

    # Walk every module in the server package, not just server.py: skills split
    # their error wrapping across helpers (`_shared.py`, `tools/*.py`), and a
    # scan of one file would silently miss those sites — reporting a clean
    # score for a surface it never looked at.
    handlers = []
    #: Locally-defined helpers that *render* an error payload, so a handler
    #: written as `return _as_error(...)` is not invisible. One skill's entire
    #: error surface scored nothing at all because its handlers call a renderer
    #: instead of inlining a literal — the scan claimed to cover the
    #: hand-written case "exhaustively" while skipping the tidier form of it.
    renderers: dict[str, list] = {}
    for source in sorted(server_dir.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8", errors="replace"))
        module_strings = {
            t.id: n.value.value
            for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
            for t in n.targets if isinstance(t, ast.Name)
        }
        for stmt in ast.walk(tree):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rets = [
                    n.value
                    for n in ast.walk(stmt)
                    if isinstance(n, ast.Return)
                    and isinstance(n.value, (ast.Dict, ast.Constant, ast.JoinedStr))
                ]
                if not rets:
                    continue
                # A renderer usually builds its hint into a local before
                # returning, so the hint is nowhere in the return expression.
                # Fold in any module-level string the function references, or
                # the tidier pattern reads as carrying no hint at all — which is
                # how one skill's real, hint-carrying payload scored zero.
                extra = " ".join(
                    module_strings[n.id]
                    for n in ast.walk(stmt)
                    if isinstance(n, ast.Name) and n.id in module_strings
                )
                renderers[stmt.name] = (rets, extra)
        # Module-level string constants of this file, so a hint hoisted into a
        # constant resolves in the file that defines it.
        consts = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    for tgt in stmt.targets:
                        if isinstance(tgt, ast.Name):
                            consts[tgt.id] = stmt.value.value
        handlers.extend(
            (n, consts) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
        )

    for handler, file_constants in handlers:
        for node in ast.walk(handler):
            if not (isinstance(node, ast.Return) and node.value is not None):
                continue
            value = node.value
            folded = ""
            if isinstance(value, ast.Call):
                fn = value.func
                fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                rendered = renderers.get(fname)
                if not rendered:
                    continue
                value, folded = rendered[0][0], rendered[1]
            if isinstance(value, ast.Dict):
                keys = {k.value for k in value.keys if isinstance(k, ast.Constant)}
                if "error" not in keys:
                    continue
                hint = ""
                for k, v in zip(value.keys, value.values):
                    if isinstance(k, ast.Constant) and k.value == "hint":
                        hint = _resolve(v)
                yield (node.lineno, True, bool(hint), hint, "items" in keys)
            elif isinstance(value, (ast.Constant, ast.JoinedStr)):
                text = _resolve(value)
                if text.lower().lstrip().startswith("error"):
                    # `folded` carries a hint the renderer assembles before
                    # returning; empty for handlers that inline their payload.
                    yield (node.lineno, False, bool(folded), f"{text} {folded}".strip(), False)


def test_tool_failure_payloads_are_self_describing(board, names_artifact):
    """Every caught-error return in the MCP server must carry a usable next step.

    This is the most-seen error surface in the skill: it wraps *all* tool
    failures, including ones whose underlying message scored well above. Two
    properties matter beyond the message text.

    A **dict with a hint** keeps a failure machine-distinguishable from a result.
    A bare ``"Error: ..."`` string is the failure mode worth naming: the model
    receives what looks like ordinary tool output, and a weak model summarises it
    to the user as a finding rather than recognising it as a fault.

    A payload carrying ``items`` would be worse still — a failed call that reads
    as a successful empty page is issue #31's exact reported symptom, so that one
    is asserted outright rather than merely scored.
    """
    sites = tuple(_error_returns_in_server())
    assert sites, "found no error returns in the MCP server — has the module moved?"

    dict_shaped = [s for s in sites if s[1]]
    with_hint = [s for s in sites if s[2]]
    actionable_hint = [s for s in sites if names_artifact(str(s[3]))]
    string_shaped = [s for s in sites if not s[1]]
    leaks_items = [s for s in sites if s[4]]

    checks = len(dict_shaped) + len(with_hint) + len(actionable_hint)
    score = board.add(
        Score(
            name="tool_failure_payload_quality",
            value=checks,
            maximum=len(sites) * 3,
            unit="checks",
            detail={
                "error_return_sites": len(sites),
                "dict_shaped": len(dict_shaped),
                "carries_hint": len(with_hint),
                "hint_names_artifact": len(actionable_hint),
                "bare_string_error_lines": [s[0] for s in string_shaped],
            },
        )
    )
    print(
        f"\n[capability] tool_failure_payload_quality = {score.pct}%  "
        f"({len(sites)} sites: {len(dict_shaped)} dict-shaped, "
        f"{len(with_hint)} with hint, {len(actionable_hint)} actionable)"
    )
    if string_shaped:
        print(f"             bare-string errors at lines: {[s[0] for s in string_shaped]}")

    assert not leaks_items, (
        "an error payload now carries 'items' — a failed call can be read as a "
        "successful empty result, which is issue #31's exact failure mode"
    )
    assert score.pct >= 30.0, "tool failure payloads no longer tell the model anything"

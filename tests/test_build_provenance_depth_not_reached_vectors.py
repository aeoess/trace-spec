"""Reference walk for the depth not-reached candidate vectors.

The conformance runner in `test_build_provenance_depth_vectors.py` already
separates the two ways a depth goes unreached: it reports `verified_depth`
alongside `unresolved`, and an empty `unresolved` at the same `verified_depth`
means the verifier never looked. That separation lives in the runner result. It
does not survive into a serialized appraisal, because `Appraisal` carries
`provenance_depth_verified` and nothing else on the depth axis.

These vectors carry the serialized appraisal each runner block would produce, and
this module rebuilds it. `provenance_depth_not_reached` is a PLACEHOLDER: it is
candidate material for issue #279, it is not in `schema/trace-claim.json`, and
nothing here adds a public API for it.

The placeholder describes the immediate next depth above
`provenance_depth_verified`. It is emitted only when the issuer-declared depth is
above the verified depth. Because depth is ordered and nested, that first
not-reached depth is derivable and does not need to be serialized again.

  `not_attempted`: the verifier stopped at the verified depth without attempting
  that next depth.
  `unresolved`: the verifier attempted to progress beyond the verified depth but
  evidence needed for the next depth did not resolve.

The registry is the same shape as `test_delegation_vectors.RULES`, for the same
reason: a check that is not registered never runs, so it cannot exist quietly.
"""
from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = _ROOT / "examples" / "build-provenance-depth-not-reached"

# The depth order. Nested, so a deeper depth carries every shallower one.
ORDER = ("surface", "builder", "transitive")


def rank(depth: str) -> int:
    return ORDER.index(depth)


def implied_target(verified_depth: str) -> str | None:
    """The depth the placeholder describes: the immediate successor of verified.

    Never the declared depth itself. Declared `transitive` over verified `surface`
    describes `builder`, because `builder` is the first depth that went unreached.
    """
    i = rank(verified_depth)
    return ORDER[i + 1] if i + 1 < len(ORDER) else None


def _declared_above_verified(v: dict[str, Any]) -> bool:
    """The trigger. Nothing is emitted for a rejected record, and nothing is
    emitted when the issuer declared no more than the verifier reached."""
    block = v["runner_result"]
    return (block["outcome"] != "reject"
            and rank(v["declared_depth"]) > rank(block["verified_depth"]))


@dataclass(frozen=True)
class Rule:
    """One registered reason the placeholder can carry."""

    code: str
    applies: Callable[[dict[str, Any]], bool]
    value: Callable[[dict[str, Any]], str]


RULES: tuple[Rule, ...] = (
    Rule(
        code="not_reached_not_attempted",
        applies=lambda v: (
            _declared_above_verified(v)
            and rank(v["attempted_depth"]) == rank(v["runner_result"]["verified_depth"])),
        value=lambda v: "not_attempted",
    ),
    Rule(
        code="not_reached_unresolved",
        applies=lambda v: (
            _declared_above_verified(v)
            and rank(v["attempted_depth"]) > rank(v["runner_result"]["verified_depth"])),
        value=lambda v: "unresolved",
    ),
)

VERIFIER = "https://verifier.example/trace"
POLICY_REF = "https://verifier.example/policy/builder-floor"
TIMESTAMP = 1756900000


def build_appraisal(vector: dict[str, Any], rules: Sequence[Rule] = RULES) -> dict[str, Any]:
    """The serialized appraisal a verifier would emit for one runner block."""
    block = vector["runner_result"]
    appraisal: dict[str, Any] = {
        "status": "contraindicated" if block["outcome"] == "reject" else "affirming",
        "verifier": VERIFIER,
        "policy_ref": POLICY_REF,
        "timestamp": TIMESTAMP,
        "provenance_depth_verified": block["verified_depth"],
    }
    for rule in rules:
        if rule.applies(vector):
            appraisal["provenance_depth_not_reached"] = rule.value(vector)
            break
    return appraisal


def load_vectors() -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(VECTORS_DIR.glob("*.json"))]


VECTOR_NAMES = [v["name"] for v in load_vectors()]


@pytest.mark.parametrize("name", VECTOR_NAMES)
def test_every_vector_reproduces_its_expected_appraisal(name: str) -> None:
    vector = next(v for v in load_vectors() if v["name"] == name)
    assert build_appraisal(vector) == vector["expected_appraisal"], name


def test_the_source_vector_each_case_reuses_exists_and_agrees() -> None:
    """Runner results are reused by path, never hand-copied."""
    for vector in load_vectors():
        source = json.loads((_ROOT / vector["source_vector"]).read_text(encoding="utf-8"))
        assert source["expected"][vector["attempted_depth"]] == vector["runner_result"], (
            f"{vector['name']} drifted from {vector['source_vector']}")


def test_the_two_reasons_are_the_only_serialized_difference() -> None:
    """The pair the gap is about: identical appraisals but for the scalar."""
    by_name = {v["name"]: v["expected_appraisal"] for v in load_vectors()}
    a = by_name["01-stopped-at-configured-floor"]
    b = by_name["02-attempted-but-unresolved"]
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert differing == {"provenance_depth_not_reached"}, differing
    assert a["provenance_depth_not_reached"] == "not_attempted"
    assert b["provenance_depth_not_reached"] == "unresolved"


def test_without_the_placeholder_the_pair_is_byte_identical() -> None:
    """The gap, restated as an assertion: strip the placeholder and the two
    appraisals are the same bytes, which is what a serialized record carries today."""
    import rfc8785

    by_name = {v["name"]: dict(v["expected_appraisal"]) for v in load_vectors()}
    a = by_name["01-stopped-at-configured-floor"]
    b = by_name["02-attempted-but-unresolved"]
    a.pop("provenance_depth_not_reached", None)
    b.pop("provenance_depth_not_reached", None)
    assert rfc8785.dumps(a) == rfc8785.dumps(b)


def test_the_placeholder_is_not_a_schema_member() -> None:
    """It is candidate material. It must not have leaked into the schema or model.

    This goes red by design the day a field of this name lands in `schema/` or
    `src/`, and needs removal or inversion then.
    """
    schema = (_ROOT / "schema" / "trace-claim.json").read_text(encoding="utf-8")
    models = (_ROOT / "src" / "agentrust_trace" / "models.py").read_text(encoding="utf-8")
    assert "provenance_depth_not_reached" not in schema
    assert "provenance_depth_not_reached" not in models


def _synthetic(declared: str, verified: str, attempted: str) -> dict[str, Any]:
    """A triple on the walk. Not a vector, and no record is authored for it."""
    return {
        "name": f"synthetic-{declared}-{verified}-{attempted}",
        "declared_depth": declared,
        "attempted_depth": attempted,
        "runner_result": {
            "outcome": "accept",
            "verified_depth": verified,
            "failures": [],
            "unresolved": ["synthetic"] if rank(attempted) > rank(verified) else [],
        },
    }


TRIPLES = [
    (d, v, a)
    for d, v, a in itertools.product(ORDER, repeat=3)
    if rank(v) <= rank(a)
]


@pytest.mark.parametrize("declared,verified,attempted", TRIPLES)
def test_the_trigger_over_every_ordered_triple(declared: str, verified: str,
                                               attempted: str) -> None:
    """Enumerate the depth lattice rather than trusting the seven vectors."""
    appraisal = build_appraisal(_synthetic(declared, verified, attempted))
    value = appraisal.get("provenance_depth_not_reached")

    # (i) present iff the declared depth is strictly above the verified depth.
    assert (value is not None) == (rank(declared) > rank(verified)), (
        declared, verified, attempted, value)

    # (ii) not_attempted iff the verifier stopped at its ceiling, unresolved iff
    # it tried to go further.
    if value is not None:
        expected = "not_attempted" if rank(attempted) == rank(verified) else "unresolved"
        assert value == expected, (declared, verified, attempted, value)

    # (iii) the described depth is the successor of verified, never the declared
    # depth when declared is two steps above verified.
    target = implied_target(verified)
    if value is not None:
        assert target is not None
        assert rank(target) == rank(verified) + 1
        if rank(declared) - rank(verified) == 2:
            assert target != declared, (declared, verified, target)


def test_two_steps_above_verified_still_describes_the_successor() -> None:
    """The named case: declared transitive, verified surface, attempted builder."""
    appraisal = build_appraisal(_synthetic("transitive", "surface", "builder"))
    assert appraisal["provenance_depth_not_reached"] == "unresolved"
    assert implied_target("surface") == "builder"
    assert implied_target("surface") != "transitive"

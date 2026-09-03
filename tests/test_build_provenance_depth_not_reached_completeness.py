"""Margin checks for the depth not-reached candidate set.

Mutates the registry in `test_build_provenance_depth_not_reached_vectors` at the
same floor the receipt corpus uses: deleting a rule must change at least two
vector outcomes, and the two must be independent, meaning a declared weakened
variant of the check deviates one of them and leaves the other undisturbed. A
clean control does not count toward the two.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.test_build_provenance_depth_not_reached_vectors import (
    RULES,
    Rule,
    build_appraisal,
    load_vectors,
)

CODES = [rule.code for rule in RULES]

# Declared defects: one weakened check per rule, minimum. The placeholder is a
# scalar, so the weakened variant still fires on the same vectors and emits the
# value carrying no reason. That is the shortcut a first implementation takes: it
# notices the declared depth went unreached and says so without saying why.
WEAKENED_EMITS_NO_REASON = set(CODES)

# The vectors that emit nothing. None of them can separate a reason rule, so none
# counts toward the two a rule must be load-bearing for. `07` is here because it
# pins the trigger's negative: declared equals verified, so nothing went unreached.
CONTROLS = {
    "05-depth-reached-no-placeholder",
    "06-contradicted-not-a-not-reached-case",
    "07-declared-builder-verified-builder-no-value",
}


def _without(code: str) -> tuple[Rule, ...]:
    return tuple(rule for rule in RULES if rule.code != code)


def _weakened(code: str) -> tuple[Rule, ...]:
    """The declared weakened variant: the rule fires and carries no reason."""
    return tuple(
        replace(rule, value=lambda v: "") if rule.code == code else rule
        for rule in RULES
    )


def _deviating(rules: tuple[Rule, ...]) -> set[str]:
    """Vector names whose expected appraisal the mutated registry no longer produces."""
    return {v["name"] for v in load_vectors()
            if build_appraisal(v, rules) != v["expected_appraisal"]}


def test_the_unmutated_registry_agrees_with_every_vector() -> None:
    assert _deviating(RULES) == set()


def test_registry_is_well_formed() -> None:
    assert len(CODES) == len(set(CODES)), "duplicate rule codes"
    assert all(isinstance(code, str) and code for code in CODES)


def test_every_non_control_vector_emits_a_value() -> None:
    """The controls are exactly the vectors that emit nothing, stated rather than assumed."""
    emitting = {v["name"] for v in load_vectors()
                if "provenance_depth_not_reached" in v["expected_appraisal"]}
    names = {v["name"] for v in load_vectors()}
    assert names - emitting == CONTROLS, sorted(names - emitting)


@pytest.mark.parametrize("code", CODES)
def test_each_rule_is_load_bearing_for_two_vectors(code: str) -> None:
    """Deleting a rule must change at least two non-control vector outcomes."""
    deviating = _deviating(_without(code)) - CONTROLS
    assert len(deviating) >= 2, (
        f"deleting {code} changes {sorted(deviating)}, which is fewer than two "
        f"non-control vectors, so the rule has no margin")


@pytest.mark.parametrize("code", sorted(WEAKENED_EMITS_NO_REASON))
def test_the_weakened_variant_separates_two_independent_vectors(code: str) -> None:
    """A weakened rule must deviate its own vectors and leave the others undisturbed.

    That is what makes the pair independent rather than two copies of one check:
    each side is separated by a different rule, so weakening either one moves
    exactly its own side.
    """
    deviating = _deviating(_weakened(code)) - CONTROLS
    assert deviating, f"weakening {code} changes nothing, so it is not load-bearing"
    undisturbed = {v["name"] for v in load_vectors()} - deviating - CONTROLS
    assert undisturbed, (
        f"weakening {code} disturbs every non-control vector, so the set does not "
        f"separate the two reasons independently")


def test_the_two_reason_rules_are_independent_of_each_other() -> None:
    """Neither reason rule can stand in for the other."""
    a = _deviating(_without("not_reached_not_attempted")) - CONTROLS
    b = _deviating(_without("not_reached_unresolved")) - CONTROLS
    assert a and b
    assert not (a & b), f"the two reason rules overlap on {sorted(a & b)}"


def test_the_declared_depth_trigger_is_load_bearing() -> None:
    """07 differs from 01 only in `declared_depth`, and only 07 emits nothing.

    Without the trigger the two would be indistinguishable, so this is the margin
    on the trigger itself rather than on either reason rule.
    """
    by_name = {v["name"]: v for v in load_vectors()}
    one = by_name["01-stopped-at-configured-floor"]
    seven = by_name["07-declared-builder-verified-builder-no-value"]
    assert one["runner_result"] == seven["runner_result"]
    assert one["source_vector"] == seven["source_vector"]
    assert one["declared_depth"] != seven["declared_depth"]
    assert "provenance_depth_not_reached" in one["expected_appraisal"]
    assert "provenance_depth_not_reached" not in seven["expected_appraisal"]


def test_no_vector_expects_a_reason_the_registry_cannot_emit() -> None:
    emitted = {rule.value(v) for rule in RULES for v in load_vectors() if rule.applies(v)}
    for vector in load_vectors():
        value = vector["expected_appraisal"].get("provenance_depth_not_reached")
        if value is not None:
            assert value in emitted, vector["name"]


def test_every_registered_rule_is_exercised_by_some_vector() -> None:
    for rule in RULES:
        assert any(rule.applies(v) for v in load_vectors()), f"{rule.code} never fires"

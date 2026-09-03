#!/usr/bin/env python3
"""Generate the depth not-reached candidate vectors.

Deterministic and byte-reproducing under the #171 guard. Every runner block is read
from the committed `examples/build-provenance-depth/` vectors by path; nothing is
hand-copied, and no signed bytes are produced or transcribed.

PLACEHOLDER. `provenance_depth_not_reached` is provisional candidate material and
is not a proposal. It is not in `schema/trace-claim.json` and this generator does
not put it there.

The placeholder describes the immediate next depth above `provenance_depth_verified`.
It is emitted only when the issuer-declared depth is above the verified depth.
Because depth is ordered and nested, that first not-reached depth is derivable and
does not need to be serialized again.

  `not_attempted`: the verifier stopped at the verified depth without attempting
  that next depth.
  `unresolved`: the verifier attempted to progress beyond the verified depth but
  evidence needed for the next depth did not resolve.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "build-provenance-depth"

# Every non-depth field of the appraisal is pinned, so a byte difference between
# two generated appraisals can only come from the depth-related content.
VERIFIER = "https://verifier.example/trace"
POLICY_REF = "https://verifier.example/policy/builder-floor"
TIMESTAMP = 1756900000

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


def not_reached_value(outcome: str, declared: str, verified: str, attempted: str) -> str | None:
    """The scalar, or None when nothing declared went unreached.

    Present iff the runner accepted and the declared depth is strictly above the
    verified depth. `not_attempted` when the verifier stopped at its own ceiling,
    `unresolved` when it tried to go further and the evidence did not resolve.
    """
    if outcome == "reject":
        return None
    if rank(declared) <= rank(verified):
        return None
    return "not_attempted" if rank(attempted) == rank(verified) else "unresolved"


# (source stem, depth attempted, declared depth, configured floor, case id, description)
CASES = [
    ("06-builder-accepts-resolved-dependencies-absent", "builder", "transitive", "builder",
     "01-stopped-at-configured-floor",
     "The issuer declares transitive. The floor is builder and the dependency walk "
     "is never attempted, so the verifier stops at its own ceiling and the runner "
     "reports verified builder with an empty unresolved list."),
    ("06-builder-accepts-resolved-dependencies-absent", "transitive", "transitive", "builder",
     "02-attempted-but-unresolved",
     "The dependency walk is attempted and its evidence does not resolve, so it "
     "caps at builder. The runner reports verified builder with a nonempty "
     "unresolved list."),
    ("04-builder-accepts-dependency-unattested", "builder", "transitive", "builder",
     "03-stopped-at-configured-floor-second-record",
     "The same stopping point on a different record, so not_attempted is "
     "load-bearing for two vectors rather than one."),
    ("04-builder-accepts-dependency-unattested", "transitive", "transitive", "builder",
     "04-attempted-but-unresolved-second-record",
     "The same unresolved outcome on a different record and a different unresolved "
     "code."),
    ("01-all-depths-accept", "transitive", "transitive", "builder",
     "05-depth-reached-no-placeholder",
     "The declared depth is reached, so nothing declared went unreached and the "
     "value is absent."),
    ("05-builder-accepts-dependency-publisher-untrusted", "transitive", "transitive", "builder",
     "06-contradicted-not-a-not-reached-case",
     "Evidence resolved and contradicts the record. That is a failure, not a depth "
     "that went unreached, so the value is absent and the appraisal is "
     "contraindicated."),
    ("06-builder-accepts-resolved-dependencies-absent", "builder", "builder", "builder",
     "07-declared-builder-verified-builder-no-value",
     "The same record and the same runner block as 01, declared builder rather "
     "than transitive. Declared equals verified, so nothing declared went "
     "unreached and the value is absent. This pins the trigger's negative."),
]


def appraisal_for(block: dict, declared: str, attempted: str) -> dict:
    """The serialized appraisal a verifier would emit for one runner block."""
    verified = block["verified_depth"]
    rejected = block["outcome"] == "reject"
    appraisal: dict = {
        "status": "contraindicated" if rejected else "affirming",
        "verifier": VERIFIER,
        "policy_ref": POLICY_REF,
        "timestamp": TIMESTAMP,
        "provenance_depth_verified": verified,
    }
    value = not_reached_value(block["outcome"], declared, verified, attempted)
    if value is not None:
        appraisal["provenance_depth_not_reached"] = value
    return appraisal


def build() -> list[tuple[Path, dict]]:
    out = []
    for stem, attempted, declared, floor, case_id, description in CASES:
        src = SOURCE / f"{stem}.json"
        vector = json.loads(src.read_text(encoding="utf-8"))
        block = vector["expected"][attempted]
        payload = {
            "name": case_id,
            "description": description,
            "source_vector": f"examples/build-provenance-depth/{stem}.json",
            "declared_depth": declared,
            "attempted_depth": attempted,
            "configured_floor": floor,
            "runner_result": block,
            "expected_appraisal": appraisal_for(block, declared, attempted),
        }
        out.append((HERE / f"{case_id}.json", payload))
    return out


def main() -> int:
    for path, payload in build():
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Depth not-reached candidate vectors

Candidate material for [#279](https://github.com/agentrust-io/trace-spec/issues/279),
"absence gets a name and a reason, per surface, not a shared null", applied to the depth
axis that [#66](https://github.com/agentrust-io/trace-spec/issues/66) says would need the
same fix.

Nothing here binds an implementation. It scores one, and it scores exactly one thing: whether
a serialized appraisal can tell the two ways a depth goes unreached apart.

**Status.** Informative. No text here carries an uppercase RFC 2119 keyword of its own.
`schema/`, `spec/` and `docs/verification.md` are untouched by this directory.

## PLACEHOLDER

`provenance_depth_not_reached`, the string in the expected appraisals below, is a
**PLACEHOLDER**. It is provisional candidate material, not a proposal, and it is deliberately
not in `schema/trace-claim.json` or in `src/agentrust_trace/models.py`.
`tests/test_build_provenance_depth_not_reached_vectors.py` asserts it has not leaked into
either. That leak test goes red by design the day a field of this name lands in `schema/` or
`src/`, and it needs removal or inversion then rather than a quiet edit.

The distinction is the claim; the serialized field shape and vocabulary are provisional.

## The gap, in bytes

The conformance runner already separates the two cases.
`examples/build-provenance-depth/README.md` says so at line 64: a verifier that stopped at
`builder` "records `builder` too, but with an empty `unresolved`: it never looked. That
difference is the separation."

That separation lives in the runner result. It does not survive serialization. `Appraisal`
(`src/agentrust_trace/models.py:294`, `extra="forbid"`) carries `status`, `verifier`,
`policy_ref`, `timestamp` and `provenance_depth_verified`, and
`schema/trace-claim.json:355` is `"additionalProperties": false` over the same five. There is
no field to receive `unresolved`, and the depth enum has three values, all of them positive
statements of work done.

Serializing the two appraisals with every non-depth field held identical, canonicalized with
the repository's own `sign._canonical_bytes` (RFC 8785):

    stopped at the configured floor      sha256 b260c6cf1ed3a03fdd372f92a96c545e79a95af622dddf0678c996c25420ffe2
    attempted, evidence unresolved       sha256 b260c6cf1ed3a03fdd372f92a96c545e79a95af622dddf0678c996c25420ffe2

Byte-identical. `tests/test_build_provenance_depth_not_reached_vectors.py::test_without_the_placeholder_the_pair_is_byte_identical`
holds that as an assertion, so the gap closing would fail the test rather than pass silently.

## What the value means

The placeholder describes the immediate next depth above `provenance_depth_verified`. It is
emitted only when the issuer-declared depth is above the verified depth. Because depth is
ordered and nested, that first not-reached depth is derivable and does not need to be
serialized again.

- `not_attempted`: the verifier stopped at the verified depth without attempting that next
  depth.
- `unresolved`: the verifier attempted to progress beyond the verified depth but evidence
  needed for the next depth did not resolve.

The depth described is always the successor of the verified depth, never the declared depth
itself. Declared `transitive` over verified `surface` describes `builder`.
`test_the_trigger_over_every_ordered_triple` enumerates the whole depth lattice rather than
trusting the seven vectors, and
`test_two_steps_above_verified_still_describes_the_successor` pins that named case.

## Trigger

The reference point is `build_provenance.provenance_depth`, the depth the issuer claims to
have walked (`spec/trace-v0.2.md` lines 366-369, where a record that omits it "MUST be treated
as `surface`"). The reused source records omit it, so each candidate vector supplies
`declared_depth` as an input beside `attempted_depth` and `configured_floor`.

Three outcomes, kept apart:

- `contraindicated` covers a verified depth below the profile floor
  (`docs/verification.md` lines 209-210).
- The value covers a declared depth above the verified depth with the floor still met. That is
  the case this directory is about, and today it is invisible in the record.
- A declared depth at or below the verified depth carries nothing, which is what `07` pins.

## What the placeholder does not carry

`spec/trace-v0.2.md` lines 378-381 says a verifier that downgrades "MUST record that lower
verified depth and identify the unresolved evidence". The placeholder carries the reason class
only. It does not identify the evidence, and it is not a substitute for doing so: the runner's
`unresolved` codes are the natural payload for that identification, and where that payload
sits belongs to the editorial shape rather than to this directory.
[#271](https://github.com/agentrust-io/trace-spec/pull/271) carries `cause` beside `outcome`
on the revocation surface the same way.

A `level` member was removed from an earlier draft of this set. Under the depth order the first
not-reached depth is the immediate successor of the verified depth and is derivable from it, so
serializing it again would restate a value the reader already holds, and it is never the
declared depth itself.

## The vectors

| Case | Source vector, reused by path | Declared | Attempted | `unresolved` | Value |
|---|---|---|---|---|---|
| `01-stopped-at-configured-floor` | `examples/build-provenance-depth/06-builder-accepts-resolved-dependencies-absent.json` | `transitive` | `builder` | empty | `not_attempted` |
| `02-attempted-but-unresolved` | same file | `transitive` | `transitive` | `resolved_dependencies_absent` | `unresolved` |
| `03-stopped-at-configured-floor-second-record` | `examples/build-provenance-depth/04-builder-accepts-dependency-unattested.json` | `transitive` | `builder` | empty | `not_attempted` |
| `04-attempted-but-unresolved-second-record` | same file | `transitive` | `transitive` | `dependency_unattested` | `unresolved` |
| `05-depth-reached-no-placeholder` | `examples/build-provenance-depth/01-all-depths-accept.json` | `transitive` | `transitive` | empty | absent |
| `06-contradicted-not-a-not-reached-case` | `examples/build-provenance-depth/05-builder-accepts-dependency-publisher-untrusted.json` | `transitive` | `transitive` | empty | absent |
| `07-declared-builder-verified-builder-no-value` | `examples/build-provenance-depth/06-builder-accepts-resolved-dependencies-absent.json` | `builder` | `builder` | empty | absent |

`01` and `02` are the pair. Their expected appraisals differ in exactly one member,
`provenance_depth_not_reached`, and that member is a string.

**No new record was authored.** The corpus already carried both sides: `06`'s `builder` block
is the stopped-at-floor case and its `transitive` block is the attempted-but-unresolved case,
on the same record. `03` and `04` repeat the pair on a second record so each reason is
load-bearing for two vectors rather than one. `07` reuses the same source and the same runner
block as `01` and differs from it only in `declared_depth`, which is what makes it the
trigger's negative rather than a second copy of an existing case.

`06` is a control in the sharper sense: evidence resolved and contradicted the record. That is
a failure, not a depth that went unreached, and `docs/verification.md` lines 221-225 is
explicit that letting a contradiction present as coverage-unavailable "would make the depth
field cover for the attack it was added to expose". The value is absent there by construction.

## Margin

`tests/test_build_provenance_depth_not_reached_completeness.py` mutates the registry in
`tests/test_build_provenance_depth_not_reached_vectors.py`. The registry is two rules,
`not_reached_not_attempted` and `not_reached_unresolved`. Deleting a rule must change at least
two non-control vector outcomes: deleting `not_reached_not_attempted` changes `01` and `03`,
and deleting `not_reached_unresolved` changes `02` and `04`, with no overlap between them.

The declared weakened variant emits the value carrying no reason, which is the shortcut a first
implementation takes: it notices the declared depth went unreached and says so without saying
why. Weakening either rule deviates its own two vectors and leaves the other two undisturbed.

`05`, `06` and `07` emit nothing, so none of them can separate a reason rule and none counts
toward the two. `test_every_non_control_vector_emits_a_value` states that set rather than
assuming it, and `test_the_declared_depth_trigger_is_load_bearing` holds the margin on the
trigger itself by pinning that `01` and `07` share a source, a runner block and everything else
serialized, and differ only in `declared_depth`.

## Regenerating

```bash
python3 examples/build-provenance-depth-not-reached/gen_not_reached_appraisals.py
```

Deterministic, and under the [#171](https://github.com/agentrust-io/trace-spec/issues/171)
byte-reproduction guard. It reads the existing vectors by path and copies no signed bytes;
there are none to copy, because the build-provenance-depth vectors are unsigned.

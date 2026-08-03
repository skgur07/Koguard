# Koguard Code Review Criteria

Reviews should start with findings rather than summaries. Prioritize real defects and regression risks over style preferences.

## Priority

- P0: Issues that immediately block release, such as data loss, arbitrary code execution, or secret exposure.
- P1: Incorrect detection behavior in normal input, public API breakage, or serious performance/security regressions.
- P2: Boundary-case failures, missing verification, or maintainability risks.
- P3: Smaller issues that are still clearly worth fixing.

## Correctness

- Is detected always equivalent to bool(matches)?
- Are matches deterministically ordered by original position, longer span, and matcher priority?
- Does whitelist removal preserve unrelated valid matches?
- Are start and end returned as half-open spans relative to the original text?
- Are Unicode-normalization and removed characters handled without shifting spans?

## Security and privacy

- Can input length or candidate count be abused to consume excessive CPU or memory?
- Are user input or detected terms unnecessarily written to logs, exceptions, or temporary files?
- Are dictionary paths and encoding errors handled safely and clearly?

## Design and compatibility

- Does the change alter public types, exceptions, or field semantics unexpectedly?
- Are engine and dictionary safe to share after construction?
- Does the change pull in optional dependencies into the core package unexpectedly?

## Testing

- Is there a failing test that reproduces the change and a passing test that validates the fix?
- Are both normal text and anti-false-positive cases covered?
- If corpus expectations changed, is the reason documented?

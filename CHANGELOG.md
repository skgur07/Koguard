# Changelog

All notable changes to Koguard are documented here. The format follows Keep a Changelog, and the project uses
Semantic Versioning after the first public release.

## [Unreleased]

### Added

- Reproducible public corpus, matcher ablation, profile reporting, and artifact audit tooling.
- `strict`, `balanced`, and `aggressive` profiles plus the `contains()` convenience API.
- Unicode format-character, combining-mark, compatibility-jamo, span, Whitelist, and adversarial regressions.
- Cross-platform CI, clean-install smoke tests, security policy, contribution guide, and source-rights ledger.
- MIT project license and Git identity normalization for the maintainer's previous `s23019` identity.
- Six independently reviewed Korean literals and three owner-selected lowercase romanized literals.
- Aggregate-only hidden evaluation attestation and PF-014 release decision report tooling.
- TestPyPI evidence contract that binds installation smoke results to audited artifact hashes.
- License-pinned KOTE and BEEP review intakes plus a duplicate-free, 30%-capped PF-005 composition.
- Aggregate-only evidence for a second 500-case blinded PF-005 review and third-review adjudication.
- Blinded matcher re-audit and source-balanced review queue tooling for the next PF-005 batches.
- Aggregate-only policy re-audit, balanced batch-002, profile, and PF-007 candidate evidence for 972
  independently finalized tuning cases.
- A disjoint 1,000-case PF-005 review buffer with 30% per-source cap, pinned source expansion, and
  project-authored hard-negative targets.
- Independent double review and third-review adjudication evidence for the first 500-case hard-negative
  buffer batch, expanding finalized tuning evidence to 1,455 cases.
- Independent review of the disjoint second 500-case hard-negative buffer batch, expanding finalized
  tuning evidence to 1,935 cases and completing case-level review of the full 1,000-case buffer.
- Profile-level blinded re-audit evidence for two shared Exact/Alias false positives, both independently
  confirmed as policy positives without exposing protected case data.
- A third disjoint 500-case balanced review batch with independent double review and adjudication,
  expanding finalized tuning evidence to 2,363 cases.

### Changed

- The no-argument engine now uses the measured `balanced` profile instead of the legacy all-enabled config.
- Public API exports are limited to implemented core contracts required for `0.1.0`.
- Wheel ZIP creator metadata is canonicalized before audit so supported OS builds are byte-identical.
- Profile limitations now report the measured hard-negative and false-positive counts instead of stale
  hard-coded sample values.
- Two apparent sentence false positives shared by strict and balanced were corrected as annotation-policy
  positives after independent re-audit; balanced retains an occurrence FP delta of six versus strict.
- Source distributions exclude the complete tuning corpus directory so newly added review buffers cannot
  enter public artifacts through an outdated per-file exclusion list.
- Review queue planning accepts validated prior queues as exclusions so later annotation batches cannot
  select an already reviewed case.
- Review queue planning also accepts prior annotation batches, reports historical cross-format overlap,
  and excludes the union before selecting a new batch.

### Security

- Maximum-input and matcher candidate bounds are enforced on adversarial Unicode, prefix, Whitelist, and gap
  paths.
- Runtime processing remains offline and does not log inspected text by default.
- GitHub private vulnerability reporting is enabled for confidential security reports.

[Unreleased]: https://github.com/skgur07/Koguard/compare/dev...HEAD

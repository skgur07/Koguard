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
- Four independently reviewed Korean literals and three owner-selected lowercase romanized literals.

### Changed

- The no-argument engine now uses the measured `balanced` profile instead of the legacy all-enabled config.
- Public API exports are limited to implemented core contracts required for `0.1.0`.

### Security

- Maximum-input and matcher candidate bounds are enforced on adversarial Unicode, prefix, Whitelist, and gap
  paths.
- Runtime processing remains offline and does not log inspected text by default.

[Unreleased]: https://github.com/skgur07/Koguard/compare/dev...HEAD

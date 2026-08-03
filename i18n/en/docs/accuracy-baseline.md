# Exact Match Accuracy Baseline

Measured: 2026-07-28

Target: Koguard Exact Match + repeated-vowel and special-character views + user-supplied whitelist

Environment: CPython 3.11.9

## Results

- Number of sentences: 16
- Expected detections: 17
- False positives: 0
- False negatives: 0
- Precision: 1.0
- Recall: 1.0

## Scope

The baseline uses the hand-authored minimum regression corpus in tests/corpus/exact_cases.json. It covers single and multiple exact matches, repeated-match cases, repeated-vowel obfuscation, special-character insertion obfuscation, normal sentences, historical whitelist reclassification cases, and an expanded default blacklist. The default whitelist is empty, and the user-supplied whitelist span-protection behavior is covered separately in unit tests.

This result is an initial baseline for detecting implementation regressions and does not represent the accuracy of a production service environment. After reviewing external datasets, the corpus size and expression variety will be expanded and the measurements will be updated.

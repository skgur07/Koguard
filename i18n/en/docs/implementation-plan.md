# Koguard Implementation Plan Review

## 1. Review conclusion

Separating Engine from Adapter and moving from a low-cost dictionary-based stage to an optional AI plugin stage is a sensible direction. Avoiding runtime network dependencies and not introducing caching also keeps the initial version simpler.

## 2. Design decisions to finalize before implementation

### 2.1 Project naming

- Project/product name: Koguard
- PyPI distribution name: koguard
- Python import name: koguard
- Default engine class: KoguardEngine

### 2.2 Match result model

The library should expose a detailed sequence of matches rather than a single matched word, because a sentence can contain multiple matches and whitelist protection only applies to specific spans.

### 2.3 Normalization

Normalization should be implemented as separate views with preserved source index mapping so that original spans remain traceable.

### 2.4 Dictionary and whitelist semantics

- Exact matching should operate on token or term spans, not the whole input string.
- Whitelist handling should remove only overlapping blacklist spans and preserve unrelated matches.
- Whitelist precedence should be deterministic.

## 3. Non-functional requirements

- Development and verification target: CPython 3.11.9
- Maximum input length should be enforced explicitly.
- Dictionary and engine instances should be safe to share across threads after construction.
- The same input and configuration should yield deterministic ordering.

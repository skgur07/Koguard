"""Public result models returned by Koguard."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class MatchMethod(StrEnum):
    """Method responsible for a profanity match."""

    EXACT = "exact"
    TRIE = "trie"
    LEVENSHTEIN = "levenshtein"
    EMBEDDING = "embedding"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Match:
    """A single match mapped to the original input when possible."""

    term: str
    matched_text: str
    start: int | None
    end: int | None
    method: MatchMethod
    score: float

    def __post_init__(self) -> None:
        if self.method is MatchMethod.NONE:
            raise ValueError("MatchMethod.NONE cannot be used for a detected match")
        if not self.term:
            raise ValueError("term must not be empty")
        if not self.matched_text:
            raise ValueError("matched_text must not be empty")
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must both be set or both be None")
        if self.start is not None and self.end is not None:
            if self.start < 0 or self.end <= self.start:
                raise ValueError("match span must satisfy 0 <= start < end")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Immutable result of checking one input string."""

    normalized_text: str
    matches: tuple[Match, ...] = ()
    elapsed_ms: float = 0.0

    def __post_init__(self) -> None:
        normalized_matches = tuple(self.matches)
        if not all(isinstance(match, Match) for match in normalized_matches):
            raise TypeError("matches must contain only Match instances")
        object.__setattr__(self, "matches", normalized_matches)

        if not isfinite(self.elapsed_ms) or self.elapsed_ms < 0.0:
            raise ValueError("elapsed_ms must be finite and non-negative")

    @property
    def detected(self) -> bool:
        """Whether at least one match was detected."""

        return bool(self.matches)

    @property
    def matched_word(self) -> str | None:
        """Canonical term of the first match for scalar API compatibility."""

        return self.matches[0].term if self.matches else None

    @property
    def method(self) -> MatchMethod:
        """Method of the first match, or NONE when no match exists."""

        return self.matches[0].method if self.matches else MatchMethod.NONE

    @property
    def confidence(self) -> float:
        """Score of the first match for scalar API compatibility."""

        return self.matches[0].score if self.matches else 0.0

"""Deterministic seed and pseudo-random generation manager for reproducible benchmark synthesis."""

import hashlib
import json
import random
from typing import Any, Sequence, TypeVar

T = TypeVar("T")


class SeedManager:
    """Encapsulates a deterministic pseudo-random number generator for reproducible generation."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._counter = 0

    @property
    def seed(self) -> int:
        """Return the base random seed."""
        return self._seed

    def reset(self, new_seed: int | None = None) -> None:
        """Reset the internal generator to the initial or new seed."""
        if new_seed is not None:
            self._seed = new_seed
        self._rng = random.Random(self._seed)
        self._counter = 0

    def choice(self, seq: Sequence[T]) -> T:
        """Deterministically choose an element from a non-empty sequence."""
        if not seq:
            raise ValueError("Cannot choose from an empty sequence.")
        return self._rng.choice(seq)

    def sample(self, seq: Sequence[T], k: int) -> list[T]:
        """Deterministically sample k unique elements from a sequence."""
        return self._rng.sample(list(seq), min(k, len(seq)))

    def shuffle(self, seq: list[T]) -> None:
        """Deterministically shuffle a list in-place."""
        self._rng.shuffle(seq)

    def randint(self, a: int, b: int) -> int:
        """Return a random integer in range [a, b] inclusive."""
        return self._rng.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """Return a random floating point number in range [a, b]."""
        return self._rng.uniform(a, b)

    def next_id(self, prefix: str) -> str:
        """Generate a deterministic, unique, prefixed identifier."""
        self._counter += 1
        digest = hashlib.sha256(
            f"{self._seed}:{self._counter}:{prefix}".encode("utf-8")
        ).hexdigest()[:8]
        return f"{prefix}-{digest}"

    def derive_seed(self, domain_label: str) -> int:
        """Derive a reproducible sub-seed for a specific sub-generator or domain."""
        digest = hashlib.sha256(f"{self._seed}:{domain_label}".encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big")


def compute_deterministic_hash(data: dict[str, Any] | list[Any]) -> str:
    """Compute SHA-256 hash over deterministic JSON serialization.

    Excludes volatile fields like timestamps or execution counters if present in metadata.
    """
    serialized = json.dumps(data, sort_keys=True, indent=None, ensure_ascii=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

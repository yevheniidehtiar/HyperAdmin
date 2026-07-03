"""Foreign-key ID pool with Pareto-skewed sampling.

A real ERP is *skewed*: a handful of "hot" accounts own most of the invoices. Benchmarks run
against uniform-random FK references understate index-seek cost and cache pressure, so the
pool draws parent IDs with an ≈80/20 Pareto skew instead of uniformly.

Sampling uses the inverse-transform of a bounded power law over the *rank* of parent IDs. If a
parent list has ``n`` entries ranked ``0..n-1`` (insertion order), the probability that a draw
lands in the top fraction ``f`` of ranks is ``f ** ((a-1)/a)``. For ``a = 1.16`` that makes the
top 20% of parents own ≈80% of references — the documented skew — with no clamping artefacts.

``numpy`` is a *soft* dependency used to vectorise :meth:`FKPool.sample_many`; without it the
pool falls back to a pure-stdlib loop over :func:`random.Random.random`. Both paths are
reproducible under a fixed seed; they are not required to produce byte-identical streams.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Vectorise sample_many through numpy only above this draw count; below it the per-call
# overhead of seeding a numpy generator outweighs the stdlib loop.
_NUMPY_MIN_N = 64

try:  # pragma: no cover - exercised indirectly via both code paths in tests
    import numpy as _np  # pyright: ignore[reportMissingImports]

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - numpy is a dev dep; fallback is still tested
    _np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


class EmptyPoolError(RuntimeError):
    """Raised when a child table samples a parent whose pool has not been populated."""


class FKPool:
    """In-memory store of inserted parent primary keys with Pareto-skewed sampling."""

    def __init__(self, *, pareto_a: float = 1.16, rng: random.Random | None = None) -> None:
        if pareto_a <= 1:
            # a <= 1 makes (a-1)/a <= 0, which inverts/flattens the skew. Guard it.
            raise ValueError("pareto_a must be > 1 for a meaningful skew")
        self._pareto_a = pareto_a
        self._exponent = pareto_a / (pareto_a - 1.0)  # = 1 / ((a-1)/a); q = u ** exponent
        self._rng = rng if rng is not None else random.Random()  # noqa: S311 - seeding RNG
        self._pools: dict[str, list[int]] = {}

    @property
    def pareto_a(self) -> float:
        return self._pareto_a

    def extend(self, table: str, pks: Iterable[int]) -> None:
        """Append freshly-inserted primary keys for ``table`` to its pool."""
        self._pools.setdefault(table, []).extend(pks)

    def size(self, table: str) -> int:
        """Number of IDs currently held for ``table`` (0 if never populated)."""
        return len(self._pools.get(table, ()))

    def __len__(self) -> int:
        """Total number of IDs held across every table."""
        return sum(len(ids) for ids in self._pools.values())

    def __contains__(self, table: object) -> bool:
        return table in self._pools

    def _require(self, table: str) -> list[int]:
        ids = self._pools.get(table)
        if not ids:
            raise EmptyPoolError(
                f"FK pool for {table!r} is empty — its parent rows must be seeded "
                "before any child that references it"
            )
        return ids

    def _skewed_index(self, n: int) -> int:
        """Return a power-law-skewed rank index in ``[0, n)`` using one stdlib draw."""
        q = self._rng.random() ** self._exponent
        idx = int(q * n)
        return idx if idx < n else n - 1

    def sample(self, table: str) -> int:
        """Return one parent ID for ``table`` drawn with the Pareto skew."""
        ids = self._require(table)
        return ids[self._skewed_index(len(ids))]

    def sample_many(self, table: str, n: int) -> list[int]:
        """Return ``n`` parent IDs for ``table`` (with replacement, Pareto-skewed)."""
        if n < 0:
            raise ValueError("n must be >= 0")
        ids = self._require(table)
        if n == 0:
            return []
        size = len(ids)
        if _HAS_NUMPY and _np is not None and n >= _NUMPY_MIN_N:
            # Vectorised fast path. Seed a local numpy generator from the shared rng so the
            # stream stays reproducible and advances the rng for subsequent draws.
            seed = self._rng.getrandbits(63)
            gen = _np.random.default_rng(seed)
            q = gen.random(n) ** self._exponent
            indices = (q * size).astype(_np.int64)
            _np.clip(indices, 0, size - 1, out=indices)
            return [ids[i] for i in indices.tolist()]
        return [ids[self._skewed_index(size)] for _ in range(n)]


__all__ = ["EmptyPoolError", "FKPool"]

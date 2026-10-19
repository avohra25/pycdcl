"""Model enumeration on top of the incremental solver."""

from __future__ import annotations

from typing import Iterable, Iterator, Sequence

from .solver import Solver


def iter_models(clauses: Iterable[Iterable[int]], project: Sequence[int] | None = None,
                limit: int | None = None) -> Iterator[list[int]]:
    """Yield distinct satisfying assignments.

    With ``project``, models are distinct on those variables only (each
    yielded list contains just the projected literals). Enumeration adds a
    blocking clause per model, so it reuses everything learnt so far.
    """
    s = Solver()
    s.add_clauses(clauses)
    if project is not None:
        for v in project:
            while s.num_vars < v:
                s.new_var()
    count = 0
    while limit is None or count < limit:
        if not s.solve():
            return
        model = s.model
        if project is None:
            picked = list(model)
        else:
            picked = [model[v - 1] for v in project]
        yield picked
        count += 1
        if not picked or not s.add_clause([-l for l in picked]):
            return


def count_models(clauses: Iterable[Iterable[int]], project: Sequence[int] | None = None) -> int:
    return sum(1 for _ in iter_models(clauses, project))

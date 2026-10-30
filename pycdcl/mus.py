"""Unsatisfiable cores and minimal unsatisfiable subsets (MUS) of clauses.

Each soft clause ``C_i`` is guarded by a fresh selector variable ``s_i`` and
added as ``C_i | ~s_i``. Solving under the assumptions ``s_1 .. s_m`` switches
every clause on; when that fails, the solver's assumption core names a subset
of clauses that is already unsatisfiable. A deletion-based loop then drops
clauses one at a time, keeping a clause only if the rest become satisfiable
without it. Each unsatisfiable probe also returns a core, which usually
discards many candidates at once (clause-set refinement), and every probe
reuses what the solver learnt on earlier ones.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .solver import Solver


class _Guarded:
    def __init__(self, soft: Sequence[Sequence[int]], hard: Iterable[Iterable[int]]) -> None:
        hard = [list(c) for c in hard]
        top = max((abs(l) for c in list(soft) + hard for l in c), default=0)
        self.solver = Solver()
        while self.solver.num_vars < top:
            self.solver.new_var()
        self.solver.add_clauses(hard)
        self.selector = []
        for c in soft:
            sel = self.solver.new_var()
            self.selector.append(sel)
            self.solver.add_clause(list(c) + [-sel])
        self.index = {sel: i for i, sel in enumerate(self.selector)}

    def probe(self, indices: Iterable[int], max_conflicts: int | None = None):
        """Solve with only ``indices`` switched on; return (result, core indices)."""
        result = self.solver.solve([self.selector[i] for i in indices],
                                   max_conflicts=max_conflicts)
        if result is False:
            return False, {self.index[l] for l in self.solver.core}
        return result, None


def unsat_core(clauses: Sequence[Sequence[int]], hard: Iterable[Iterable[int]] = (),
               minimal: bool = True, max_conflicts: int | None = None) -> list[int] | None:
    """Return 0-based indices of an unsatisfiable subset of ``clauses``.

    ``hard`` clauses are always present and never reported. Returns None if
    ``clauses`` plus ``hard`` is satisfiable. With ``minimal`` (the default)
    the result is a MUS: unsatisfiable, but satisfiable once any one of its
    clauses is removed. An empty list means ``hard`` alone is
    unsatisfiable. ``max_conflicts`` bounds each solver call; if a
    minimisation probe runs out, that clause is conservatively kept, so the
    result is still unsatisfiable but may not be minimal.

    >>> unsat_core([[1, 2], [-1], [3], [-2], [3, 4]])
    [0, 1, 3]
    >>> unsat_core([[1, 2], [-1]]) is None
    True
    """
    clauses = [list(c) for c in clauses]
    g = _Guarded(clauses, hard)
    result, core = g.probe(range(len(clauses)), max_conflicts)
    if result is not False:
        if result is None:
            raise RuntimeError("conflict budget exhausted before unsatisfiability was shown")
        return None
    if not minimal:
        return sorted(core)
    critical: set[int] = set()
    work = sorted(core, reverse=True)
    while work:
        i = work.pop()
        rest = work + sorted(critical)
        result, sub = g.probe(rest, max_conflicts)
        if result is False:
            # Clause i is not needed; the new core may rule out more.
            work = [j for j in work if j in sub]
        else:
            critical.add(i)   # removing i makes the rest satisfiable (or unknown)
    return sorted(critical)


def is_mus(clauses: Sequence[Sequence[int]], indices: Sequence[int],
           hard: Iterable[Iterable[int]] = ()) -> bool:
    """Check that ``indices`` select a minimal unsatisfiable subset."""
    clauses = [list(c) for c in clauses]
    g = _Guarded(clauses, hard)
    if g.probe(indices)[0] is not False:
        return False
    return all(g.probe([j for j in indices if j != i])[0] is True for i in indices)

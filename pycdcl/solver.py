"""A conflict-driven clause learning (CDCL) SAT solver.

Literals use DIMACS conventions at the API boundary (``3`` is variable 3,
``-3`` its negation). Internally variable ``v`` (0-based) maps to literal
``2*v`` for the positive phase and ``2*v + 1`` for the negative phase, so
negation is ``lit ^ 1`` and the variable is ``lit >> 1``.

Techniques: two watched literals, first-UIP clause learning with
local (one-step) learnt clause minimisation, non-chronological
backjumping, VSIDS branching with an indexed heap, phase saving, Luby
restarts and activity-based learnt clause deletion.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ._heap import VarHeap

TRUE, FALSE, UNASSIGNED = 1, -1, 0


def luby(y: float, i: int) -> float:
    """Return the i-th element (0-based) of the Luby sequence scaled by y."""
    size, seq = 1, 0
    while size < i + 1:
        seq += 1
        size = 2 * size + 1
    while size - 1 != i:
        size = (size - 1) >> 1
        seq -= 1
        i %= size
    return y ** seq


class Clause:
    __slots__ = ("lits", "learnt", "activity", "deleted")

    def __init__(self, lits: list[int], learnt: bool = False) -> None:
        self.lits = lits
        self.learnt = learnt
        self.activity = 0.0
        self.deleted = False

    def __repr__(self) -> str:
        return f"Clause({[_to_dimacs(l) for l in self.lits]})"


def _to_dimacs(lit: int) -> int:
    v = (lit >> 1) + 1
    return -v if lit & 1 else v


def _to_internal(lit: int) -> int:
    if lit == 0:
        raise ValueError("0 is not a literal")
    return ((abs(lit) - 1) << 1) | (lit < 0)


class Stats:
    __slots__ = ("decisions", "propagations", "conflicts", "restarts",
                 "learnt_literals", "minimised_literals", "reductions")

    def __init__(self) -> None:
        for name in self.__slots__:
            setattr(self, name, 0)

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__slots__}


class Solver:
    """Incremental CDCL SAT solver.

    >>> s = Solver()
    >>> s.add_clause([1, 2]); s.add_clause([-1, 2]); s.add_clause([-2, 3])
    True
    True
    True
    >>> s.solve()
    True
    >>> s.value(2), s.value(3)
    (True, True)
    >>> s.solve(assumptions=[-3])
    False
    """

    def __init__(self, *, var_decay: float = 0.95, clause_decay: float = 0.999,
                 restart_first: int = 100, restart_inc: float = 2.0,
                 learnt_ratio: float = 1 / 3, learnt_growth: float = 1.1,
                 min_learnts: int = 100) -> None:
        self.var_decay = var_decay
        self.clause_decay = clause_decay
        self.restart_first = restart_first
        self.restart_inc = restart_inc
        self.learnt_ratio = learnt_ratio
        self.learnt_growth = learnt_growth
        self.min_learnts = min_learnts

        self.num_vars = 0
        self.clauses: list[Clause] = []
        self.learnts: list[Clause] = []
        self.watches: list[list[Clause]] = []   # per literal
        self.vals: list[int] = []               # per literal: TRUE/FALSE/UNASSIGNED
        self.level: list[int] = []              # per variable
        self.reason: list[Clause | None] = []   # per variable
        self.polarity: list[int] = []           # per variable: saved phase bit
        self.activity: list[float] = []         # per variable
        self.seen: list[bool] = []              # per variable, scratch for analyze
        self.order = VarHeap(self.activity)
        self.trail: list[int] = []
        self.trail_lim: list[int] = []
        self.qhead = 0
        self.var_inc = 1.0
        self.cla_inc = 1.0
        self.max_learnts = 0.0
        self.ok = True
        self.model: list[int] | None = None
        self.stats = Stats()

    # ------------------------------------------------------------------ setup

    def new_var(self) -> int:
        """Create a fresh variable and return its DIMACS number."""
        v = self.num_vars
        self.num_vars += 1
        self.watches.append([])
        self.watches.append([])
        self.vals.append(UNASSIGNED)
        self.vals.append(UNASSIGNED)
        self.level.append(0)
        self.reason.append(None)
        self.polarity.append(1)
        self.activity.append(0.0)
        self.seen.append(False)
        self.order.grow(self.num_vars)
        self.order.insert(v)
        return v + 1

    def _ensure_vars(self, lits: Iterable[int]) -> None:
        top = max((abs(l) for l in lits), default=0)
        while self.num_vars < top:
            self.new_var()

    def add_clause(self, lits: Iterable[int]) -> bool:
        """Add a clause of DIMACS literals.

        Returns False if the formula became trivially unsatisfiable. May only
        be called between solves (the solver is always at decision level 0
        then).
        """
        lits = list(lits)
        self._ensure_vars(lits)
        if not self.ok:
            return False
        vals = self.vals
        out: list[int] = []
        present = set()
        for ext in lits:
            lit = _to_internal(ext)
            if lit ^ 1 in present or vals[lit] == TRUE:
                return True  # tautology or already satisfied at level 0
            if lit in present or vals[lit] == FALSE:
                continue
            present.add(lit)
            out.append(lit)
        if not out:
            self.ok = False
            return False
        if len(out) == 1:
            self._enqueue(out[0], None)
            self.ok = self._propagate() is None
            return self.ok
        c = Clause(out)
        self.clauses.append(c)
        self._attach(c)
        return True

    def add_clauses(self, clauses: Iterable[Iterable[int]]) -> bool:
        ok = True
        for c in clauses:
            ok = self.add_clause(c) and ok
        return ok

    # -------------------------------------------------------------- queries

    def value(self, var: int) -> bool | None:
        """Truth value of ``var`` in the last model (None if unknown)."""
        if self.model is None or not 1 <= var <= len(self.model):
            return None
        return self.model[var - 1] > 0

    # ------------------------------------------------------------ internals

    def _attach(self, c: Clause) -> None:
        self.watches[c.lits[0]].append(c)
        self.watches[c.lits[1]].append(c)

    def _decision_level(self) -> int:
        return len(self.trail_lim)

    def _enqueue(self, lit: int, reason: Clause | None) -> None:
        v = lit >> 1
        self.vals[lit] = TRUE
        self.vals[lit ^ 1] = FALSE
        self.level[v] = len(self.trail_lim)
        self.reason[v] = reason
        self.trail.append(lit)

    def _propagate(self) -> Clause | None:
        """Unit propagation over two watched literals; return a conflict."""
        vals, watches, trail = self.vals, self.watches, self.trail
        level, reason = self.level, self.reason
        props = 0
        confl = None
        while self.qhead < len(trail):
            false_lit = trail[self.qhead] ^ 1
            self.qhead += 1
            props += 1
            ws = watches[false_lit]
            i = j = 0
            n = len(ws)
            dl = len(self.trail_lim)
            while i < n:
                c = ws[i]
                i += 1
                lits = c.lits
                if lits[0] == false_lit:
                    lits[0] = lits[1]
                    lits[1] = false_lit
                first = lits[0]
                if vals[first] == TRUE:
                    ws[j] = c
                    j += 1
                    continue
                for k in range(2, len(lits)):
                    lk = lits[k]
                    if vals[lk] != FALSE:
                        lits[1] = lk
                        lits[k] = false_lit
                        watches[lk].append(c)
                        break
                else:
                    ws[j] = c
                    j += 1
                    if vals[first] == FALSE:
                        confl = c
                        while i < n:
                            ws[j] = ws[i]
                            j += 1
                            i += 1
                        self.qhead = len(trail)
                    else:
                        v = first >> 1
                        vals[first] = TRUE
                        vals[first ^ 1] = FALSE
                        level[v] = dl
                        reason[v] = c
                        trail.append(first)
            del ws[j:]
            if confl is not None:
                break
        self.stats.propagations += props
        return confl

    def _cancel_until(self, lvl: int) -> None:
        if len(self.trail_lim) <= lvl:
            return
        vals, reason, polarity, order = self.vals, self.reason, self.polarity, self.order
        trail = self.trail
        stop = self.trail_lim[lvl]
        for idx in range(len(trail) - 1, stop - 1, -1):
            lit = trail[idx]
            v = lit >> 1
            vals[lit] = UNASSIGNED
            vals[lit ^ 1] = UNASSIGNED
            reason[v] = None
            polarity[v] = lit & 1
            order.insert(v)
        del trail[stop:]
        del self.trail_lim[lvl:]
        self.qhead = len(trail)

    def _bump_var(self, v: int) -> None:
        act = self.activity
        act[v] += self.var_inc
        if act[v] > 1e100:
            for i in range(len(act)):
                act[i] *= 1e-100
            self.var_inc *= 1e-100
        self.order.increased(v)

    def _bump_clause(self, c: Clause) -> None:
        c.activity += self.cla_inc
        if c.activity > 1e20:
            for lc in self.learnts:
                lc.activity *= 1e-20
            self.cla_inc *= 1e-20

    def _analyze(self, confl: Clause) -> tuple[list[int], int]:
        """First-UIP conflict analysis. Returns (learnt clause, backjump level).

        The asserting literal is placed first and a literal from the
        backjump level second, ready to be watched.
        """
        seen, level, reason, trail = self.seen, self.level, self.reason, self.trail
        dl = len(self.trail_lim)
        learnt = [0]
        counter = 0
        p = -1
        idx = len(trail) - 1
        to_clear: list[int] = []
        while True:
            if confl.learnt:
                self._bump_clause(confl)
            lits = confl.lits
            for q in (lits if p == -1 else lits[1:]):
                v = q >> 1
                if not seen[v] and level[v] > 0:
                    seen[v] = True
                    to_clear.append(v)
                    self._bump_var(v)
                    if level[v] >= dl:
                        counter += 1
                    else:
                        learnt.append(q)
            while not seen[trail[idx] >> 1]:
                idx -= 1
            p = trail[idx]
            idx -= 1
            counter -= 1
            if counter == 0:
                break
            confl = reason[p >> 1]
        learnt[0] = p ^ 1

        # Minimise: drop literals implied by the rest of the clause (one step).
        before = len(learnt)
        kept = [learnt[0]]
        for q in learnt[1:]:
            r = reason[q >> 1]
            if r is None or any(not seen[x >> 1] and level[x >> 1] > 0 for x in r.lits[1:]):
                kept.append(q)
        learnt = kept
        self.stats.minimised_literals += before - len(learnt)
        for v in to_clear:
            seen[v] = False

        if len(learnt) == 1:
            return learnt, 0
        best = 1
        for i in range(2, len(learnt)):
            if level[learnt[i] >> 1] > level[learnt[best] >> 1]:
                best = i
        learnt[1], learnt[best] = learnt[best], learnt[1]
        return learnt, level[learnt[1] >> 1]

    def _pick_branch(self) -> int:
        order, vals, polarity = self.order, self.vals, self.polarity
        while len(order):
            v = order.pop()
            if vals[v << 1] == UNASSIGNED:
                return (v << 1) | polarity[v]
        return -1

    def _locked(self, c: Clause) -> bool:
        first = c.lits[0]
        return self.vals[first] == TRUE and self.reason[first >> 1] is c

    def _reduce_db(self) -> None:
        """Delete roughly half of the learnt clauses, least active first."""
        self.stats.reductions += 1
        learnts = sorted(self.learnts, key=lambda c: (len(c.lits) > 2, c.activity))
        limit = self.cla_inc / max(len(learnts), 1)
        half = len(learnts) // 2
        keep = []
        for i, c in enumerate(learnts):
            if len(c.lits) > 2 and not self._locked(c) and (i < half or c.activity < limit):
                c.deleted = True
            else:
                keep.append(c)
        self.learnts = keep
        for ws in self.watches:
            if ws:
                ws[:] = [c for c in ws if not c.deleted]

    def _search(self, budget: float, assumptions: Sequence[int]) -> bool | None:
        stats = self.stats
        conflicts = 0
        while True:
            confl = self._propagate()
            if confl is not None:
                stats.conflicts += 1
                conflicts += 1
                if not self.trail_lim:
                    self.ok = False
                    return False
                learnt, bt = self._analyze(confl)
                self._cancel_until(bt)
                stats.learnt_literals += len(learnt)
                if len(learnt) == 1:
                    self._enqueue(learnt[0], None)
                else:
                    c = Clause(learnt, learnt=True)
                    self.learnts.append(c)
                    self._attach(c)
                    self._bump_clause(c)
                    self._enqueue(learnt[0], c)
                self.var_inc /= self.var_decay
                self.cla_inc /= self.clause_decay
                continue

            if conflicts >= budget:
                self._cancel_until(0)
                return None
            if len(self.learnts) - len(self.trail) >= self.max_learnts:
                self._reduce_db()

            nxt = -1
            while len(self.trail_lim) < len(assumptions):
                p = assumptions[len(self.trail_lim)]
                if self.vals[p] == TRUE:
                    self.trail_lim.append(len(self.trail))  # dummy level
                elif self.vals[p] == FALSE:
                    return False  # unsatisfiable under the assumptions
                else:
                    nxt = p
                    break
            if nxt == -1:
                nxt = self._pick_branch()
                if nxt == -1:
                    self.model = [
                        (v + 1) if self.vals[v << 1] == TRUE else -(v + 1)
                        for v in range(self.num_vars)
                    ]
                    return True
                stats.decisions += 1
            self.trail_lim.append(len(self.trail))
            self._enqueue(nxt, None)

    # ----------------------------------------------------------------- solve

    def solve(self, assumptions: Iterable[int] = (),
              max_conflicts: int | None = None) -> bool | None:
        """Decide satisfiability, optionally under assumption literals.

        Returns True (model in ``self.model``), False, or None if
        ``max_conflicts`` was exhausted first. Unsatisfiability under
        assumptions does not poison the solver; later calls can drop them.
        """
        assumptions = list(assumptions)
        self._ensure_vars(assumptions)
        self.model = None
        if not self.ok:
            return False
        assumps = [_to_internal(l) for l in assumptions]
        self.max_learnts = max(len(self.clauses) * self.learnt_ratio, float(self.min_learnts))
        start = self.stats.conflicts
        status = None
        restarts = 0
        while status is None:
            budget = luby(self.restart_inc, restarts) * self.restart_first
            if max_conflicts is not None:
                remaining = max_conflicts - (self.stats.conflicts - start)
                if remaining <= 0:
                    break
                budget = min(budget, remaining)
            status = self._search(budget, assumps)
            if status is None:
                restarts += 1
                self.stats.restarts += 1
                self.max_learnts *= self.learnt_growth
        self._cancel_until(0)
        return status


def solve(clauses: Iterable[Iterable[int]], assumptions: Iterable[int] = ()) -> list[int] | None:
    """Convenience wrapper: return a model (list of signed ints) or None."""
    s = Solver()
    s.add_clauses(clauses)
    return s.model if s.solve(assumptions) else None


def check_model(clauses: Iterable[Iterable[int]], model: Sequence[int]) -> bool:
    """True iff ``model`` satisfies every clause."""
    true = {l for l in model}
    return all(any(l in true for l in c) for c in clauses)

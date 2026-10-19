"""Helpers for building CNF formulas: cardinality constraints and puzzles."""

from __future__ import annotations

from typing import Iterable, Sequence

from .solver import Solver


class CNF:
    """A growable clause list with a fresh-variable counter."""

    def __init__(self, num_vars: int = 0) -> None:
        self.num_vars = num_vars
        self.clauses: list[list[int]] = []

    def new_var(self) -> int:
        self.num_vars += 1
        return self.num_vars

    def new_vars(self, n: int) -> list[int]:
        return [self.new_var() for _ in range(n)]

    def add(self, clause: Iterable[int]) -> None:
        clause = list(clause)
        for l in clause:
            if l == 0:
                raise ValueError("0 is not a literal")
            self.num_vars = max(self.num_vars, abs(l))
        self.clauses.append(clause)

    def extend(self, clauses: Iterable[Iterable[int]]) -> None:
        for c in clauses:
            self.add(c)

    # ----------------------------------------------------- cardinality

    def at_least_one(self, lits: Sequence[int]) -> None:
        self.add(lits)

    def at_most_one(self, lits: Sequence[int]) -> None:
        """Pairwise encoding for small groups, sequential counter otherwise."""
        if len(lits) <= 6:
            for i in range(len(lits)):
                for j in range(i + 1, len(lits)):
                    self.add([-lits[i], -lits[j]])
        else:
            self.at_most_k(lits, 1)

    def exactly_one(self, lits: Sequence[int]) -> None:
        self.at_least_one(lits)
        self.at_most_one(lits)

    def at_most_k(self, lits: Sequence[int], k: int) -> None:
        """Sinz's sequential counter: O(n*k) auxiliary variables and clauses.

        Register ``s[i][j]`` means "at least j+1 of lits[0..i] are true".
        """
        n = len(lits)
        if k < 0:
            raise ValueError("k must be non-negative")
        if k >= n:
            return
        if k == 0:
            for l in lits:
                self.add([-l])
            return
        s = [self.new_vars(k) for _ in range(n - 1)]
        self.add([-lits[0], s[0][0]])
        for j in range(1, k):
            self.add([-s[0][j]])
        for i in range(1, n - 1):
            self.add([-lits[i], s[i][0]])
            self.add([-s[i - 1][0], s[i][0]])
            for j in range(1, k):
                self.add([-lits[i], -s[i - 1][j - 1], s[i][j]])
                self.add([-s[i - 1][j], s[i][j]])
            self.add([-lits[i], -s[i - 1][k - 1]])
        self.add([-lits[n - 1], -s[n - 2][k - 1]])

    def at_least_k(self, lits: Sequence[int], k: int) -> None:
        """At least k of lits, as at most len-k of their negations."""
        if k <= 0:
            return
        if k > len(lits):
            self.add([])  # impossible
            return
        self.at_most_k([-l for l in lits], len(lits) - k)

    def exactly_k(self, lits: Sequence[int], k: int) -> None:
        self.at_most_k(lits, k)
        self.at_least_k(lits, k)

    # ---------------------------------------------------------- solving

    def solver(self) -> Solver:
        s = Solver()
        for _ in range(self.num_vars):
            s.new_var()
        s.add_clauses(self.clauses)
        return s

    def solve(self) -> list[int] | None:
        s = self.solver()
        return s.model if s.solve() else None


# ---------------------------------------------------------------- puzzles

def sudoku(grid: str) -> str | None:
    """Solve a 9x9 sudoku given as 81 chars ('.' or '0' for blanks).

    Returns the solved grid as an 81-char string, or None if impossible.
    """
    cells = [ch for ch in grid if not ch.isspace()]
    if len(cells) != 81:
        raise ValueError("sudoku grid must have 81 cells")
    var = lambda r, c, d: r * 81 + c * 9 + d + 1  # noqa: E731
    cnf = CNF(729)
    for r in range(9):
        for c in range(9):
            cnf.exactly_one([var(r, c, d) for d in range(9)])
    for d in range(9):
        for i in range(9):
            cnf.exactly_one([var(i, c, d) for c in range(9)])
            cnf.exactly_one([var(r, i, d) for r in range(9)])
            br, bc = 3 * (i // 3), 3 * (i % 3)
            cnf.exactly_one([var(br + a, bc + b, d) for a in range(3) for b in range(3)])
    for idx, ch in enumerate(cells):
        if ch in ".0":
            continue
        if not ch.isdigit():
            raise ValueError(f"bad sudoku cell {ch!r}")
        cnf.add([var(idx // 9, idx % 9, int(ch) - 1)])
    model = cnf.solve()
    if model is None:
        return None
    out = []
    for r in range(9):
        for c in range(9):
            out.append(next(str(d + 1) for d in range(9) if model[var(r, c, d) - 1] > 0))
    return "".join(out)


def n_queens(n: int) -> list[int] | None:
    """Place n non-attacking queens; returns the column of the queen in each row."""
    if n < 1:
        raise ValueError("n must be positive")
    var = lambda r, c: r * n + c + 1  # noqa: E731
    cnf = CNF(n * n)
    for r in range(n):
        cnf.exactly_one([var(r, c) for c in range(n)])
    for c in range(n):
        cnf.at_most_one([var(r, c) for r in range(n)])
    for d in range(-(n - 1), n):
        diag = [var(r, r - d) for r in range(n) if 0 <= r - d < n]
        anti = [var(r, d + n - 1 - r) for r in range(n) if 0 <= d + n - 1 - r < n]
        if len(diag) > 1:
            cnf.at_most_one(diag)
        if len(anti) > 1:
            cnf.at_most_one(anti)
    model = cnf.solve()
    if model is None:
        return None
    return [next(c for c in range(n) if model[var(r, c) - 1] > 0) for r in range(n)]


def pigeonhole(pigeons: int, holes: int) -> CNF:
    """The classic PHP formula: unsatisfiable whenever pigeons > holes."""
    var = lambda p, h: p * holes + h + 1  # noqa: E731
    cnf = CNF(pigeons * holes)
    for p in range(pigeons):
        cnf.add([var(p, h) for h in range(holes)])
    for h in range(holes):
        for a in range(pigeons):
            for b in range(a + 1, pigeons):
                cnf.add([-var(a, h), -var(b, h)])
    return cnf


def graph_coloring(edges: Iterable[tuple[int, int]], k: int) -> dict[int, int] | None:
    """Colour the graph's nodes with k colours so no edge is monochrome."""
    edges = list(edges)
    nodes = sorted({u for e in edges for u in e})
    index = {u: i for i, u in enumerate(nodes)}
    var = lambda u, c: index[u] * k + c + 1  # noqa: E731
    cnf = CNF(len(nodes) * k)
    for u in nodes:
        cnf.exactly_one([var(u, c) for c in range(k)])
    for u, v in edges:
        if u == v:
            return None
        for c in range(k):
            cnf.add([-var(u, c), -var(v, c)])
    model = cnf.solve()
    if model is None:
        return None
    return {u: next(c for c in range(k) if model[var(u, c) - 1] > 0) for u in nodes}

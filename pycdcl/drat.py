"""A forward checker for DRUP proofs of unsatisfiability.

A DRUP proof is a text file of lemmas, one clause per line in DIMACS
literal syntax (``1 -3 0``), plus deletion lines (``d 1 -3 0``) that remove a
clause from the working set. A lemma is accepted if it has the *reverse unit
propagation* (RUP) property: assigning every literal in it false and
unit-propagating over the current clauses yields a conflict. The proof is
valid when every lemma is RUP and the empty clause is eventually derived.

This is the subset of DRAT that CDCL solvers without inprocessing produce,
including ``Solver(proof=...)``. Lemmas that need the resolution asymmetric
tautology (RAT) check are reported as failures. As in drat-trim, deleting a
unit clause is ignored, since a unit's consequences stay valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


class ProofError(ValueError):
    """Raised for proof text that cannot be parsed."""


@dataclass
class CheckResult:
    verified: bool
    message: str
    lemmas: int = 0          # lemmas checked
    deletions: int = 0       # deletion lines applied
    failed_line: int | None = None

    def __bool__(self) -> bool:
        return self.verified


def parse_proof(text: str) -> Iterator[tuple[int, bool, list[int]]]:
    """Yield ``(line number, is_deletion, literals)`` for each proof step."""
    for lineno, raw in enumerate(text.splitlines(), 1):
        toks = raw.split()
        if not toks or toks[0] == "c":
            continue
        delete = toks[0] == "d"
        if delete:
            toks = toks[1:]
        try:
            lits = [int(t) for t in toks]
        except ValueError:
            raise ProofError(f"line {lineno}: bad literal in {raw.strip()!r}") from None
        if not lits or lits[-1] != 0 or 0 in lits[:-1]:
            raise ProofError(f"line {lineno}: clause must end with a single 0")
        yield lineno, delete, lits[:-1]


def _code(lit: int) -> int:
    return (abs(lit) << 1) | (lit < 0)


class _Checker:
    """Clause database with two-watched-literal propagation from scratch."""

    def __init__(self) -> None:
        self.vals: list[int] = []      # per literal code: 1 true, -1 false, 0 open
        self.watches: list[list[list[int]]] = []
        self.units: list[int] = []
        self.index: dict[tuple[int, ...], list[list[int]]] = {}
        self.has_empty = False

    def _grow(self, code: int) -> None:
        while len(self.vals) <= (code | 1):
            self.vals.append(0)
            self.watches.append([])

    def add(self, lits: Iterable[int]) -> None:
        codes = sorted({_code(l) for l in lits})
        if any(c ^ 1 in codes for c in codes):
            return   # tautologies never propagate
        for c in codes:
            self._grow(c)
        if not codes:
            self.has_empty = True
        elif len(codes) == 1:
            self.units.append(codes[0])
        else:
            clause = list(codes)
            self.watches[clause[0]].append(clause)
            self.watches[clause[1]].append(clause)
            self.index.setdefault(tuple(codes), []).append(clause)

    def delete(self, lits: Iterable[int]) -> bool:
        """Remove one copy of a clause; False if it is not present."""
        key = tuple(sorted({_code(l) for l in lits}))
        if len(key) <= 1:
            return True   # unit and empty deletions are ignored
        bucket = self.index.get(key)
        if not bucket:
            return False
        clause = bucket.pop()
        if not bucket:
            del self.index[key]
        for w in clause[:2]:
            ws = self.watches[w]
            # Remove by identity: duplicate clauses are equal but distinct.
            for i, other in enumerate(ws):
                if other is clause:
                    ws[i] = ws[-1]
                    ws.pop()
                    break
        return True

    def rup(self, lits: list[int]) -> bool:
        """Does assuming every literal of ``lits`` false propagate to a conflict?"""
        if self.has_empty:
            return True
        vals, watches = self.vals, self.watches
        for l in lits:
            self._grow(_code(l))
        trail: list[int] = []

        def assign(code: int) -> bool:
            v = vals[code]
            if v == -1:
                return False
            if v == 0:
                vals[code] = 1
                vals[code ^ 1] = -1
                trail.append(code)
            return True

        conflict = False
        for code in self.units:
            if not assign(code):
                conflict = True
                break
        if not conflict:
            for l in lits:
                if not assign(_code(l) ^ 1):
                    conflict = True   # lemma is a tautology or clashes with a unit
                    break
        head = 0
        while not conflict and head < len(trail):
            false_lit = trail[head] ^ 1
            head += 1
            ws = watches[false_lit]
            i = 0
            while i < len(ws):
                c = ws[i]
                if c[0] == false_lit:
                    c[0], c[1] = c[1], c[0]
                first = c[0]
                if vals[first] == 1:
                    i += 1
                    continue
                for k in range(2, len(c)):
                    if vals[c[k]] != -1:
                        c[1], c[k] = c[k], c[1]
                        watches[c[1]].append(c)
                        ws[i] = ws[-1]
                        ws.pop()
                        break
                else:
                    i += 1
                    if vals[first] == -1:
                        conflict = True
                        break
                    assign(first)
        for code in trail:
            vals[code] = vals[code ^ 1] = 0
        return conflict


def check_proof(clauses: Iterable[Iterable[int]], proof: str) -> CheckResult:
    """Verify a DRUP refutation of ``clauses``.

    >>> check_proof([[1, 2], [-1, 2], [1, -2], [-1, -2]], "1 0\\n0\\n").verified
    True
    >>> check_proof([[1, 2], [-1, 2]], "0\\n").message
    'line 1: lemma 0 is not implied by unit propagation'
    """
    checker = _Checker()
    for c in clauses:
        checker.add(c)
    lemmas = deletions = 0
    try:
        for lineno, delete, lits in parse_proof(proof):
            if delete:
                if not checker.delete(lits):
                    return CheckResult(False, f"line {lineno}: deleted clause "
                                       f"{' '.join(map(str, lits))} 0 is not in the formula",
                                       lemmas, deletions, lineno)
                deletions += 1
                continue
            if not checker.rup(lits):
                shown = " ".join(map(str, lits + [0]))
                return CheckResult(False, f"line {lineno}: lemma {shown} is not implied by unit propagation",
                                   lemmas, deletions, lineno)
            lemmas += 1
            if not lits:
                return CheckResult(True, f"empty clause derived at line {lineno}", lemmas, deletions)
            checker.add(lits)
    except ProofError as exc:
        return CheckResult(False, str(exc), lemmas, deletions)
    if checker.rup([]):
        return CheckResult(True, "conflict by unit propagation after the last lemma", lemmas, deletions)
    return CheckResult(False, "proof ends without deriving the empty clause", lemmas, deletions)

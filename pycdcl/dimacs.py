"""Reading and writing CNF formulas in DIMACS format."""

from __future__ import annotations

from typing import Iterable, TextIO


class DimacsError(ValueError):
    """Raised for malformed DIMACS input."""


def parse(text: str) -> tuple[int, list[list[int]]]:
    """Parse DIMACS CNF text into ``(num_vars, clauses)``.

    Clauses may span lines or share a line. Comment lines (``c ...``) are
    ignored, and a ``%`` line (used by the SATLIB benchmark files) ends the
    formula. A missing ``p cnf`` header is tolerated; the variable count is
    then inferred from the literals.
    """
    declared_vars = None
    declared_clauses = None
    clauses: list[list[int]] = []
    current: list[int] = []
    max_var = 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] == "c":
            continue
        if line[0] == "%":
            break
        if line[0] == "p":
            parts = line.split()
            if len(parts) != 4 or parts[1] != "cnf":
                raise DimacsError(f"line {lineno}: bad problem line {line!r}")
            if declared_vars is not None:
                raise DimacsError(f"line {lineno}: duplicate problem line")
            try:
                declared_vars, declared_clauses = int(parts[2]), int(parts[3])
            except ValueError:
                raise DimacsError(f"line {lineno}: bad problem line {line!r}") from None
            if declared_vars < 0 or declared_clauses < 0:
                raise DimacsError(f"line {lineno}: negative counts in problem line")
            continue
        for tok in line.split():
            try:
                lit = int(tok)
            except ValueError:
                raise DimacsError(f"line {lineno}: bad literal {tok!r}") from None
            if lit == 0:
                clauses.append(current)
                current = []
            else:
                current.append(lit)
                max_var = max(max_var, abs(lit))
    if current:
        clauses.append(current)
    if declared_vars is not None and max_var > declared_vars:
        raise DimacsError(
            f"literal uses variable {max_var} but header declares {declared_vars}"
        )
    if declared_clauses is not None and len(clauses) != declared_clauses:
        raise DimacsError(
            f"header declares {declared_clauses} clauses but found {len(clauses)}"
        )
    return (declared_vars if declared_vars is not None else max_var), clauses


def load(fp: TextIO) -> tuple[int, list[list[int]]]:
    """Parse DIMACS from an open text file."""
    return parse(fp.read())


def dumps(clauses: Iterable[Iterable[int]], num_vars: int | None = None,
          comments: Iterable[str] = ()) -> str:
    """Serialise clauses to DIMACS text."""
    clauses = [list(c) for c in clauses]
    if num_vars is None:
        num_vars = max((abs(l) for c in clauses for l in c), default=0)
    out = [f"c {c}" for c in comments]
    out.append(f"p cnf {num_vars} {len(clauses)}")
    out.extend(" ".join(map(str, c + [0])) for c in clauses)
    return "\n".join(out) + "\n"

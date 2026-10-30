"""Command-line front end.

    pycdcl FILE.cnf [--stats] [--max-conflicts N] [--assume LITS]
                                                     solve a DIMACS file ('-' = stdin)
    pycdcl mus FILE.cnf [--no-minimize]              print a minimal unsatisfiable subset
    pycdcl sudoku GRID                               solve an 81-char sudoku
    pycdcl queens N                                  place N queens

Exit codes follow the SAT competition convention: 10 SAT, 20 UNSAT,
0 unknown (conflict budget exhausted), 1 usage or input error.
"""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .dimacs import DimacsError, dumps, parse
from .encode import n_queens, sudoku
from .mus import unsat_core
from .solver import Solver, check_model

EXIT_SAT, EXIT_UNSAT, EXIT_UNKNOWN, EXIT_ERROR = 10, 20, 0, 1


def _format_model(model: list[int], width: int = 78) -> list[str]:
    lines, cur = [], "v"
    for tok in [str(l) for l in model] + ["0"]:
        if len(cur) + 1 + len(tok) > width:
            lines.append(cur)
            cur = "v"
        cur += " " + tok
    lines.append(cur)
    return lines


def _parse_assumptions(text: str | None) -> list[int]:
    if not text:
        return []
    lits = []
    for tok in text.replace(",", " ").split():
        try:
            lit = int(tok)
        except ValueError:
            raise ValueError(f"bad assumption literal {tok!r}") from None
        if lit == 0:
            raise ValueError("0 is not a literal")
        lits.append(lit)
    return lits


def _read_cnf(path: str) -> tuple[int, list[list[int]]]:
    if path == "-":
        return parse(sys.stdin.read())
    with open(path, encoding="utf-8") as fp:
        return parse(fp.read())


def _mus(args: argparse.Namespace, out) -> int:
    try:
        num_vars, clauses = _read_cnf(args.file)
    except (OSError, DimacsError) as exc:
        print(f"c error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    t0 = time.perf_counter()
    core = unsat_core(clauses, minimal=not args.no_minimize)
    elapsed = time.perf_counter() - t0
    if core is None:
        print("s SATISFIABLE", file=out)
        return EXIT_SAT
    kind = "core" if args.no_minimize else "minimal unsatisfiable subset"
    comments = [f"{kind}: {len(core)} of {len(clauses)} clauses, {elapsed:.3f}s",
                "original clause numbers (1-based): " + " ".join(str(i + 1) for i in core)]
    print("s UNSATISFIABLE", file=out)
    out.write(dumps([clauses[i] for i in core], num_vars, comments))
    return EXIT_UNSAT


def _solve_file(args: argparse.Namespace, out) -> int:
    try:
        assumptions = _parse_assumptions(args.assume)
    except ValueError as exc:
        print(f"c error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        num_vars, clauses = _read_cnf(args.file)
    except (OSError, DimacsError) as exc:
        print(f"c error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    t0 = time.perf_counter()
    s = Solver()
    while s.num_vars < num_vars:
        s.new_var()
    s.add_clauses(clauses)
    result = s.solve(assumptions, max_conflicts=args.max_conflicts)
    elapsed = time.perf_counter() - t0
    if args.stats:
        print(f"c vars {num_vars} clauses {len(clauses)} time {elapsed:.3f}s", file=out)
        for k, v in s.stats.as_dict().items():
            print(f"c {k} {v}", file=out)
    if result is True:
        assert check_model(clauses, s.model), "internal error: model check failed"
        print("s SATISFIABLE", file=out)
        if not args.quiet:
            for line in _format_model(s.model):
                print(line, file=out)
        return EXIT_SAT
    if result is False:
        print("s UNSATISFIABLE", file=out)
        if assumptions:
            # An empty core means the formula is unsatisfiable on its own.
            core = " ".join(map(str, sorted(s.core, key=abs)))
            print(f"c core {core}".rstrip(), file=out)
        return EXIT_UNSAT
    print("s UNKNOWN", file=out)
    return EXIT_UNKNOWN


def _sudoku(args: argparse.Namespace, out) -> int:
    try:
        solved = sudoku(args.grid)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if solved is None:
        print("no solution", file=out)
        return EXIT_UNSAT
    for r in range(9):
        row = solved[9 * r: 9 * r + 9]
        print(" ".join(row[0:3]), "|", " ".join(row[3:6]), "|", " ".join(row[6:9]), file=out)
        if r in (2, 5):
            print("------+-------+------", file=out)
    return EXIT_SAT


def _queens(args: argparse.Namespace, out) -> int:
    if args.n < 1:
        print("error: n must be positive", file=sys.stderr)
        return EXIT_ERROR
    cols = n_queens(args.n)
    if cols is None:
        print("no solution", file=out)
        return EXIT_UNSAT
    for c in cols:
        print(" ".join("Q" if i == c else "." for i in range(args.n)), file=out)
    return EXIT_SAT


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "mus":
        p = argparse.ArgumentParser(prog="pycdcl mus",
                                    description="Print a minimal unsatisfiable subset of a CNF as DIMACS.")
        p.add_argument("file", help="DIMACS CNF file, or '-' for stdin")
        p.add_argument("--no-minimize", action="store_true",
                       help="stop at the first core instead of shrinking it to a MUS")
        return _mus(p.parse_args(argv[1:]), out)
    if argv and argv[0] in ("sudoku", "queens"):
        p = argparse.ArgumentParser(prog=f"pycdcl {argv[0]}")
        if argv[0] == "sudoku":
            p.add_argument("grid", help="81 characters, '.' or '0' for blanks")
            return _sudoku(p.parse_args(argv[1:]), out)
        p.add_argument("n", type=int)
        return _queens(p.parse_args(argv[1:]), out)

    p = argparse.ArgumentParser(prog="pycdcl", description="CDCL SAT solver for DIMACS CNF files.",
                                epilog="subcommands: 'pycdcl mus FILE', 'pycdcl sudoku GRID', 'pycdcl queens N'")
    p.add_argument("file", help="DIMACS CNF file, or '-' for stdin")
    p.add_argument("--stats", action="store_true", help="print search statistics as comments")
    p.add_argument("-q", "--quiet", action="store_true", help="omit the model ('v' lines)")
    p.add_argument("--max-conflicts", type=int, default=None, metavar="N",
                   help="give up (s UNKNOWN) after N conflicts")
    p.add_argument("--assume", metavar="LITS", default=None,
                   help="solve under assumption literals, e.g. '1 -3' or '1,-3'; "
                        "on UNSAT prints the failed ones as 'c core ...'")
    p.add_argument("--version", action="version", version=f"pycdcl {__version__}")
    return _solve_file(p.parse_args(argv), out)


if __name__ == "__main__":
    sys.exit(main())

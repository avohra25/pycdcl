"""Small reproducible benchmark: python benchmarks/bench.py [--quick]"""

from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pycdcl import Solver, check_model  # noqa: E402
from pycdcl.encode import n_queens, pigeonhole, sudoku  # noqa: E402

HARD_SUDOKU = "8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4.."


def random_3sat(rng, n, ratio=4.26):
    return [[rng.choice((1, -1)) * v for v in rng.sample(range(1, n + 1), 3)]
            for _ in range(int(ratio * n))]


def run_cnf(name, clauses):
    s = Solver()
    s.add_clauses(clauses)
    t0 = time.perf_counter()
    result = s.solve()
    dt = time.perf_counter() - t0
    if result:
        assert check_model(clauses, s.model)
    verdict = "SAT" if result else "UNSAT"
    print(f"| {name:<28} | {verdict:<6} | {s.stats.conflicts:>9} | {dt:>8.2f} |")


def run_timed(name, fn):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    print(f"| {name:<28} | {'SAT' if out is not None else 'UNSAT':<6} | {'-':>9} | {dt:>8.2f} |")


def main():
    quick = "--quick" in sys.argv
    print(f"| {'instance':<28} | {'result':<6} | {'conflicts':>9} | {'time (s)':>8} |")
    print(f"|{'-' * 30}|{'-' * 8}|{'-' * 11}|{'-' * 10}|")
    sizes = (50, 100) if quick else (50, 100, 150, 200)
    for n in sizes:
        rng = random.Random(n)
        for i in range(3):
            run_cnf(f"random 3-SAT n={n} #{i + 1}", random_3sat(rng, n))
    for p in ((6, 7) if quick else (6, 7, 8)):
        run_cnf(f"pigeonhole {p}->{p - 1}", pigeonhole(p, p - 1).clauses)
    run_timed("sudoku (Arto Inkala)", lambda: sudoku(HARD_SUDOKU))
    for n in ((8, 20) if quick else (8, 20, 40)):
        run_timed(f"{n}-queens", lambda n=n: n_queens(n))


if __name__ == "__main__":
    main()

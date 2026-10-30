# pycdcl

A small, readable **conflict-driven clause learning (CDCL) SAT solver** in pure
Python, with zero dependencies. It implements the core ideas behind MiniSat in
about 500 lines you can read in one sitting, plus the tooling to actually use
it: a DIMACS reader/writer, cardinality-constraint encoders, puzzle encoders,
model enumeration, unsatisfiable cores, checkable proofs of
unsatisfiability and a SAT-competition-style command-line solver.

```
$ python -m pycdcl examples/small.cnf
s SATISFIABLE
v 1 2 -3 0

$ python -m pycdcl --stats -q examples/php-7-6.cnf
c vars 42 clauses 133 time 0.044s
c decisions 1079
c propagations 10436
c conflicts 870
c restarts 6
...
s UNSATISFIABLE
```

## Features

- **Two watched literals** for unit propagation, so backtracking is free.
- **First-UIP conflict analysis** with one-step learnt clause minimisation and
  **non-chronological backjumping**.
- **VSIDS** branching over an indexed binary heap, with **phase saving**.
- **Luby restarts** and **activity-based learnt clause deletion** (binary and
  "locked" reason clauses are always kept).
- **Incremental solving**: add clauses between calls and solve under
  **assumptions** without losing learnt clauses.
- **Unsatisfiable cores over assumptions**: after a failed solve,
  `Solver.core` names the assumptions that are jointly to blame, found by
  final conflict analysis.
- **Minimal unsatisfiable subsets (MUS)**: `pycdcl.mus.unsat_core` shrinks
  an unsatisfiable formula to a set of clauses where every clause matters,
  using selector variables, deletion-based minimisation and core refinement.
- **Proofs of unsatisfiability**: `Solver(proof=f)` writes a DRUP proof
  (every learnt clause and deletion), and `pycdcl.drat.check_proof` /
  `pycdcl check` verify it independently of the solver.
- **Conflict budgets** (`max_conflicts`) that return "unknown" instead of
  running forever.
- **Encoders**: at-most-one, at-most/at-least/exactly-k (Sinz sequential
  counter), sudoku, N-queens, pigeonhole and graph colouring.
- **Model enumeration** with optional projection onto a subset of variables.
- **CLI** that speaks DIMACS and uses the competition exit codes (10 SAT,
  20 UNSAT, 0 unknown).

## Install

Requires Python 3.9+.

```
pip install .            # or just run from a checkout: python -m pycdcl ...
```

## Library usage

Literals follow DIMACS conventions: variable `3` is `3`, its negation `-3`.

```python
from pycdcl import Solver

s = Solver()
s.add_clauses([[1, 2], [-1, 2], [-2, 3]])
s.solve()                       # True
s.model                         # [-1, 2, 3]
s.value(3)                      # True

s.solve(assumptions=[-3])       # False: unsatisfiable under the assumption
s.solve()                       # True again; assumptions don't stick

s.solve(assumptions=[4, 1, -3]) # False
s.core                          # [-3, 1]: 1 forces 2, which forces 3
s.failed(4)                     # False: assumption 4 played no part

s.add_clause([-3])              # incremental: learnt clauses are kept
s.solve()                       # False
```

An UNSAT answer can come with a proof that a separate checker replays:

```python
import io
from pycdcl import Solver
from pycdcl.drat import check_proof

clauses = [[1, 2], [-1, 2], [1, -2], [-1, -2]]
proof = io.StringIO()
s = Solver(proof=proof)
s.add_clauses(clauses)
s.solve()                                     # False
check_proof(clauses, proof.getvalue())        # CheckResult(verified=True, ...)
```

Encoders build plain clause lists you can hand to any solver:

```python
from pycdcl.encode import CNF, sudoku, n_queens, graph_coloring
from pycdcl.models import count_models

cnf = CNF()
xs = cnf.new_vars(6)
cnf.exactly_k(xs, 2)            # sequential counter, adds auxiliary variables
count_models(cnf.clauses, project=xs)   # 15 == C(6, 2)

from pycdcl.mus import unsat_core, is_mus

unsat_core([[1, 2], [-1], [3], [-2], [3, 4]])   # [0, 1, 3]: indices of a MUS
unsat_core([[3], [1], [4]], hard=[[-1]])         # [1]: hard clauses are never reported

sudoku("53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79")
n_queens(8)                     # [1, 3, 5, 7, 2, 0, 6, 4]: queen's column in each row
graph_coloring([(1, 2), (2, 3), (3, 1)], 2)   # None: a triangle needs 3 colours
```

## Command line

```
pycdcl FILE.cnf [--stats] [-q] [--max-conflicts N] [--assume LITS] [--proof OUT]
                                                      # '-' reads stdin
pycdcl check FILE.cnf PROOF                           # verify a DRUP proof
pycdcl mus FILE.cnf [--no-minimize]                   # print a MUS as DIMACS
pycdcl sudoku GRID                                    # 81 chars, '.' or '0' blank
pycdcl queens N
```

Output follows the SAT competition format: an `s` status line, `v` model
lines wrapped at 78 columns and ending in `0`, and `c` comment lines for
statistics. Every model is checked against the input before it is printed.

`--assume "1 -3"` solves under assumption literals. If that is
unsatisfiable, a `c core ...` line lists the assumptions responsible (an
empty `c core` means the formula is unsatisfiable without any of them):

```
$ python -m pycdcl --assume "1 3" examples/small.cnf
s UNSATISFIABLE
c core 1 3
```

`--proof OUT` writes a DRUP proof alongside the answer, and `pycdcl check`
verifies it (exit code 0 when verified, 1 otherwise). The proof is written in
the standard text DRAT format used in SAT competitions, so it can also be
fed to external checkers such as drat-trim:

```
$ python -m pycdcl -q --proof php.drup examples/php-7-6.cnf
s UNSATISFIABLE
$ python -m pycdcl check examples/php-7-6.cnf php.drup
c lemmas 870 deletions 742 time 0.035s
c empty clause derived at line 1612
s VERIFIED
```

`pycdcl mus` explains *why* a formula is unsatisfiable by printing a minimal
unsatisfiable subset of its clauses as a DIMACS file, with the original clause
numbers in a comment (`--no-minimize` stops at the first core found):

```
$ printf 'p cnf 4 5\n1 2 0\n-1 0\n3 0\n-2 0\n3 4 0\n' | python -m pycdcl mus -
s UNSATISFIABLE
c minimal unsatisfiable subset: 3 of 5 clauses, 0.000s
c original clause numbers (1-based): 1 2 4
p cnf 4 3
1 2 0
-1 0
-2 0
```

## How it works

**Literal encoding.** Variable `v` (0-based) becomes literal `2v` (positive) or
`2v+1` (negative), so negation is `lit ^ 1` and `vals` is indexed directly by
literal. That keeps the hot loop free of `abs()` and sign checks.

**Propagation.** Each clause watches its first two literals. When a watched
literal becomes false the solver looks for a replacement that is not false; if
none exists the clause is either unit (the other watch is implied, with this
clause as its reason) or conflicting. Watch lists are compacted in place, and
nothing has to be undone on backtrack.

**Conflict analysis.** Starting from the conflicting clause, the solver
resolves backwards along the trail with reason clauses until exactly one
literal from the current decision level remains: the first unique implication
point. Literals from lower levels form the rest of the learnt clause; any whose
own reason is already covered by the clause are dropped. The solver jumps back
to the second-highest level in the learnt clause, where it is unit, and
asserts the UIP literal.

**Heuristics.** Variables seen during analysis are bumped by a growing
increment (equivalent to decaying all others) and kept in a max-heap; the next
decision is the most active unassigned variable, using the phase it last had.
Restarts follow the Luby sequence (`100 * luby(2, i)` conflicts). When the
number of learnt clauses exceeds a limit that grows 10% per restart, the least
active half is deleted, keeping binaries and clauses that are currently the
reason for an assignment.

**Assumptions** are decided first, one per decision level, before any
heuristic decision. An assumption that is already false means unsatisfiable
under those assumptions, but the formula itself is untouched. To say *which*
assumptions were at fault, the solver walks the implication graph backwards
from the falsified assumption, following reason clauses, and collects the
assumption decisions it reaches (MiniSat's `analyzeFinal`). The result is a
core: a subset of the assumptions that is already inconsistent with the
formula. It is not guaranteed to be minimal.

**Proofs.** Every clause the solver learns follows from the input and earlier
learnt clauses by *reverse unit propagation* (RUP): assume all its literals
false, unit-propagate, and a conflict appears. So the solver only has to log
each learnt clause as it is added (`1 -3 0`), each deleted clause as it is
dropped (`d 1 -3 0`), and the empty clause at the final level-0 conflict. The
checker in `pycdcl/drat.py` shares no code with the solver: it keeps its own
two-watched-literal clause database and, for each lemma, re-runs unit
propagation from the input's unit clauses plus the negated lemma, so a bug in
the solver's search or learning shows up as a rejected lemma rather than a
wrong answer. Only RUP lemmas are supported (no RAT), which covers everything
a CDCL solver without preprocessing produces. A proof certifies that the
formula itself is unsatisfiable; a failed solve under assumptions, or clauses
added after the input, are not covered.

**MUS extraction** builds on that. Each clause `C_i` gets a selector variable
`s_i` and is added as `C_i | ~s_i`, so assuming `s_i` switches the clause on.
Solving with every selector assumed gives a first core. The deletion loop then
tries each remaining clause in turn: if the formula stays unsatisfiable
without it, the clause is dropped, and the new core usually drops several
others at once; if the formula becomes satisfiable, the clause is critical and
stays. All probes run on one incremental solver, so learnt clauses carry over.

## Benchmarks

`python benchmarks/bench.py` on a Linux VM (Intel Xeon, CPython 3.13). Random
3-SAT instances are at the 4.26 clause/variable phase transition, which is
where they are hardest. Times are wall clock for the solve only.

| instance                     | result | conflicts | time (s) |
|------------------------------|--------|-----------|----------|
| random 3-SAT n=50 #1         | UNSAT  |        59 |     0.00 |
| random 3-SAT n=50 #2         | UNSAT  |        93 |     0.00 |
| random 3-SAT n=50 #3         | SAT    |        78 |     0.00 |
| random 3-SAT n=100 #1        | SAT    |        40 |     0.00 |
| random 3-SAT n=100 #2        | SAT    |       294 |     0.02 |
| random 3-SAT n=100 #3        | UNSAT  |       518 |     0.03 |
| random 3-SAT n=150 #1        | UNSAT  |      2859 |     0.25 |
| random 3-SAT n=150 #2        | SAT    |       791 |     0.06 |
| random 3-SAT n=150 #3        | UNSAT  |      3308 |     0.29 |
| random 3-SAT n=200 #1        | SAT    |     12470 |     2.19 |
| random 3-SAT n=200 #2        | UNSAT  |     10462 |     1.63 |
| random 3-SAT n=200 #3        | UNSAT  |     29411 |    10.10 |
| pigeonhole 6->5              | UNSAT  |       162 |     0.01 |
| pigeonhole 7->6              | UNSAT  |       870 |     0.04 |
| pigeonhole 8->7              | UNSAT  |      7283 |     0.66 |
| sudoku (Arto Inkala)         | SAT    |         - |     0.05 |
| 8-queens                     | SAT    |         - |     0.01 |
| 20-queens                    | SAT    |         - |     0.08 |
| 40-queens                    | SAT    |         - |     0.63 |

Pure Python is far slower than C++ solvers like MiniSat, so this is a teaching
and scripting tool, not a competition solver. Pigeonhole formulas
are exponentially hard for any resolution-based solver, which is why they make
a good stress test.

## Testing

```
python -m unittest discover -s tests
```

The suite cross-checks the solver against brute force on over two thousand random
small formulas (with and without assumptions, and with clauses added
incrementally), checks every model it returns, verifies the cardinality
encoders by counting models for every `n <= 7` and `k`, checks assumption
cores and MUS results against brute force on random formulas, verifies the
solver's proofs for every unsatisfiable test formula (including runs with
heavy learnt clause deletion) while rejecting tampered and truncated ones,
and exercises the CLI end to end.

## Layout

```
pycdcl/solver.py   CDCL solver
pycdcl/_heap.py    indexed max-heap for VSIDS
pycdcl/dimacs.py   DIMACS parsing and writing
pycdcl/encode.py   cardinality constraints and puzzle encoders
pycdcl/models.py   model enumeration and counting
pycdcl/mus.py      unsatisfiable cores and MUS extraction
pycdcl/drat.py     DRUP proof checker
pycdcl/cli.py      command-line front end
benchmarks/        benchmark script
examples/          sample CNF files
```

## License

MIT, see [LICENSE](LICENSE).

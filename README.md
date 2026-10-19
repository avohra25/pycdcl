# pycdcl

A small, readable conflict-driven clause learning (CDCL) SAT solver in pure
Python, with no dependencies.

Work in progress: the core solver (two watched literals, first-UIP learning,
backjumping, VSIDS with phase saving) and a DIMACS reader/writer are in place.

```python
from pycdcl import Solver

s = Solver()
s.add_clauses([[1, 2], [-1, 2], [-2, 3]])
print(s.solve(), s.model)          # True [-1, 2, 3]
print(s.solve(assumptions=[-3]))   # False
```

Run the tests with `python -m unittest discover -s tests`.

MIT licensed.

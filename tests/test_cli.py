import contextlib
import io
import os
import tempfile
import unittest

from pycdcl.cli import main


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stderr(io.StringIO()):
        code = main(argv, out=out)
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def write(self, text):
        fd, path = tempfile.mkstemp(suffix=".cnf")
        with os.fdopen(fd, "w") as fp:
            fp.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_sat(self):
        code, out = run([self.write("p cnf 3 2\n1 -2 0\n2 3 0\n")])
        self.assertEqual(code, 10)
        lines = out.splitlines()
        self.assertEqual(lines[0], "s SATISFIABLE")
        model = [int(t) for line in lines[1:] for t in line.split()[1:]]
        self.assertEqual(model[-1], 0)
        self.assertEqual(len(model), 4)

    def test_unsat_with_stats(self):
        code, out = run(["--stats", self.write("p cnf 1 2\n1 0\n-1 0\n")])
        self.assertEqual(code, 20)
        self.assertIn("s UNSATISFIABLE", out)
        self.assertIn("c conflicts", out)

    def test_unknown_on_budget(self):
        clauses = []
        var = lambda p, h: p * 7 + h + 1  # noqa: E731
        clauses = [[var(p, h) for h in range(7)] for p in range(8)]
        for h in range(7):
            for a in range(8):
                for b in range(a + 1, 8):
                    clauses.append([-var(a, h), -var(b, h)])
        text = f"p cnf 56 {len(clauses)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in clauses)
        code, out = run(["--max-conflicts", "5", "-q", self.write(text)])
        self.assertEqual(code, 0)
        self.assertIn("s UNKNOWN", out)

    def test_long_models_wrap(self):
        n = 60
        text = f"p cnf {n} {n}\n" + "".join(f"{i} 0\n" for i in range(1, n + 1))
        code, out = run([self.write(text)])
        self.assertEqual(code, 10)
        self.assertTrue(all(len(line) <= 78 for line in out.splitlines()))

    def test_bad_input(self):
        code, _ = run([self.write("p cnf 1 1\n5 0\n")])
        self.assertEqual(code, 1)
        code, _ = run(["/nonexistent/file.cnf"])
        self.assertEqual(code, 1)

    def test_sudoku_and_queens(self):
        grid = "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79"
        code, out = run(["sudoku", grid])
        self.assertEqual(code, 10)
        self.assertEqual(out.splitlines()[0], "5 3 4 | 6 7 8 | 9 1 2")
        code, out = run(["queens", "6"])
        self.assertEqual(code, 10)
        self.assertEqual(sum(line.count("Q") for line in out.splitlines()), 6)
        code, out = run(["queens", "3"])
        self.assertEqual(code, 20)

import itertools
import unittest

from pycdcl import check_model
from pycdcl.encode import CNF, graph_coloring, n_queens, pigeonhole, sudoku
from pycdcl.models import count_models, iter_models

PUZZLE = "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79"
# A puzzle often listed as one of the hardest for human solvers.
HARD = "8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4.."


def popcount_models(n, pred):
    return sum(1 for bits in itertools.product((0, 1), repeat=n) if pred(sum(bits)))


class CardinalityTests(unittest.TestCase):
    def test_at_most_k_and_exactly_k_count(self):
        for n in range(1, 8):
            xs = list(range(1, n + 1))
            for k in range(0, n + 1):
                with self.subTest(n=n, k=k):
                    c = CNF(n)
                    c.at_most_k(xs, k)
                    self.assertEqual(count_models(c.clauses, xs), popcount_models(n, lambda s: s <= k))
                    c = CNF(n)
                    c.at_least_k(xs, k)
                    self.assertEqual(count_models(c.clauses, xs), popcount_models(n, lambda s: s >= k))
                    c = CNF(n)
                    c.exactly_k(xs, k)
                    self.assertEqual(count_models(c.clauses, xs), popcount_models(n, lambda s: s == k))

    def test_at_most_one_large_group_uses_counter(self):
        c = CNF(10)
        c.exactly_one(list(range(1, 11)))
        self.assertGreater(c.num_vars, 10)
        self.assertEqual(count_models(c.clauses, list(range(1, 11))), 10)

    def test_at_least_more_than_available(self):
        c = CNF(2)
        c.at_least_k([1, 2], 3)
        self.assertIsNone(c.solve())

    def test_zero_literal_rejected(self):
        with self.assertRaises(ValueError):
            CNF().add([0])


class PuzzleTests(unittest.TestCase):
    def assertValidSudoku(self, given, solved):
        self.assertEqual(len(solved), 81)
        for i, ch in enumerate(given):
            if ch not in ".0":
                self.assertEqual(solved[i], ch)
        groups = []
        for i in range(9):
            groups.append(solved[9 * i: 9 * i + 9])
            groups.append(solved[i::9])
            br, bc = 3 * (i // 3), 3 * (i % 3)
            groups.append("".join(solved[9 * (br + a) + bc + b] for a in range(3) for b in range(3)))
        for g in groups:
            self.assertEqual(sorted(g), list("123456789"))

    def test_sudoku(self):
        for grid in (PUZZLE, HARD):
            with self.subTest(grid=grid):
                self.assertValidSudoku(grid, sudoku(grid))

    def test_sudoku_contradiction(self):
        self.assertIsNone(sudoku("11" + "." * 79))

    def test_sudoku_bad_input(self):
        with self.assertRaises(ValueError):
            sudoku("123")

    def test_n_queens(self):
        self.assertIsNone(n_queens(2))
        self.assertIsNone(n_queens(3))
        for n in (1, 4, 8, 12):
            cols = n_queens(n)
            self.assertEqual(sorted(cols), list(range(n)))
            for r1, r2 in itertools.combinations(range(n), 2):
                self.assertNotEqual(abs(cols[r1] - cols[r2]), r2 - r1)

    def test_four_queens_has_two_solutions(self):
        n = 4
        cnf = CNF(n * n)
        var = lambda r, c: r * n + c + 1  # noqa: E731
        for r in range(n):
            cnf.exactly_one([var(r, c) for c in range(n)])
        for c in range(n):
            cnf.at_most_one([var(r, c) for r in range(n)])
        for r1, r2 in itertools.combinations(range(n), 2):
            for c1 in range(n):
                for c2 in range(n):
                    if abs(c1 - c2) == r2 - r1:
                        cnf.add([-var(r1, c1), -var(r2, c2)])
        self.assertEqual(count_models(cnf.clauses, list(range(1, n * n + 1))), 2)

    def test_pigeonhole(self):
        self.assertIsNone(pigeonhole(6, 5).solve())
        cnf = pigeonhole(5, 5)
        model = cnf.solve()
        self.assertTrue(check_model(cnf.clauses, model))
        self.assertEqual(count_models(pigeonhole(4, 4).clauses), 24)

    def test_graph_coloring(self):
        triangle_plus = [(1, 2), (2, 3), (3, 1), (3, 4)]
        colours = graph_coloring(triangle_plus, 3)
        for u, v in triangle_plus:
            self.assertNotEqual(colours[u], colours[v])
        self.assertIsNone(graph_coloring(triangle_plus, 2))
        k4 = list(itertools.combinations(range(4), 2))
        self.assertIsNone(graph_coloring(k4, 3))
        self.assertIsNotNone(graph_coloring(k4, 4))


class ModelEnumerationTests(unittest.TestCase):
    def test_counts_all_models(self):
        self.assertEqual(count_models([[1, 2]]), 3)
        self.assertEqual(count_models([[1], [-1]]), 0)
        self.assertEqual(count_models([], project=[1, 2, 3]), 8)

    def test_models_are_distinct_and_valid(self):
        clauses = [[1, 2, 3], [-1, -2], [-2, -3]]
        models = list(iter_models(clauses))
        self.assertEqual(len({tuple(m) for m in models}), len(models))
        for m in models:
            self.assertTrue(check_model(clauses, m))
        self.assertEqual(len(models), 4)

    def test_limit(self):
        self.assertEqual(len(list(iter_models([], project=[1, 2, 3, 4], limit=5))), 5)

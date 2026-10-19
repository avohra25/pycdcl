import random
import unittest

from pycdcl import Solver, check_model, luby, solve

from helpers import brute_force_sat, pigeonhole_clauses, random_3sat, random_cnf


class BasicTests(unittest.TestCase):
    def test_empty_formula_is_sat(self):
        s = Solver()
        self.assertTrue(s.solve())
        self.assertEqual(s.model, [])

    def test_empty_clause_is_unsat(self):
        s = Solver()
        self.assertFalse(s.add_clause([]))
        self.assertFalse(s.solve())

    def test_unit_conflict(self):
        s = Solver()
        s.add_clause([1])
        self.assertFalse(s.add_clause([-1]))
        self.assertFalse(s.solve())

    def test_tautologies_and_duplicates(self):
        s = Solver()
        s.add_clause([1, -1, 2])
        s.add_clause([2, 2, -3, -3])
        self.assertEqual(len(s.clauses), 1)
        self.assertEqual(s.clauses[0].lits, [2, 5])  # internal encoding of 2, -3
        self.assertTrue(s.solve())

    def test_simple_implication_chain(self):
        clauses = [[1], [-1, 2], [-2, 3], [-3, 4]]
        self.assertEqual(solve(clauses), [1, 2, 3, 4])

    def test_value_and_model(self):
        s = Solver()
        s.add_clauses([[1, 2], [-1], [-2, -3]])
        self.assertTrue(s.solve())
        self.assertEqual((s.value(1), s.value(2), s.value(3)), (False, True, False))
        self.assertIsNone(s.value(4))

    def test_zero_literal_rejected(self):
        with self.assertRaises(ValueError):
            Solver().add_clause([1, 0])

    def test_luby(self):
        self.assertEqual([luby(2, i) for i in range(15)],
                         [1, 1, 2, 1, 1, 2, 4, 1, 1, 2, 1, 1, 2, 4, 8])


class AgainstBruteForce(unittest.TestCase):
    def test_random_small_formulas(self):
        rng = random.Random(1234)
        for _ in range(600):
            n = rng.randint(1, 10)
            clauses = random_cnf(rng, n, rng.randint(1, 45), width=4)
            s = Solver(restart_first=rng.choice((1, 4, 100)))
            s.add_clauses(clauses)
            result = s.solve()
            self.assertEqual(result, brute_force_sat(n, clauses), clauses)
            if result:
                self.assertTrue(check_model(clauses, s.model))

    def test_assumptions_are_incremental(self):
        rng = random.Random(99)
        for _ in range(250):
            n = rng.randint(2, 9)
            clauses = random_cnf(rng, n, rng.randint(1, 30))
            s = Solver(restart_first=2)
            s.add_clauses(clauses)
            for _ in range(4):
                assumptions = sorted({rng.choice((1, -1)) * rng.randint(1, n)
                                      for _ in range(rng.randint(0, 3))})
                if any(-a in assumptions for a in assumptions):
                    continue
                expected = brute_force_sat(n, clauses, assumptions)
                self.assertEqual(s.solve(assumptions), expected)
                if expected:
                    self.assertTrue(check_model(clauses + [[a] for a in assumptions], s.model))

    def test_adding_clauses_between_solves(self):
        rng = random.Random(7)
        for _ in range(100):
            n = rng.randint(3, 9)
            s = Solver()
            seen = []
            for _ in range(6):
                batch = random_cnf(rng, n, rng.randint(1, 8))
                seen.extend(batch)
                s.add_clauses(batch)
                self.assertEqual(s.solve(), brute_force_sat(n, seen))


class HarderInstances(unittest.TestCase):
    def test_pigeonhole_is_unsat(self):
        for p in (4, 5, 6, 7):
            with self.subTest(pigeons=p):
                s = Solver()
                s.add_clauses(pigeonhole_clauses(p, p - 1))
                self.assertFalse(s.solve())
                self.assertGreater(s.stats.conflicts, 0)

    def test_pigeonhole_fits_when_enough_holes(self):
        clauses = pigeonhole_clauses(6, 6)
        model = solve(clauses)
        self.assertIsNotNone(model)
        self.assertTrue(check_model(clauses, model))

    def test_random_3sat_threshold(self):
        rng = random.Random(42)
        sat = unsat = 0
        for _ in range(6):
            clauses = random_3sat(rng, 80)
            s = Solver()
            s.add_clauses(clauses)
            if s.solve():
                sat += 1
                self.assertTrue(check_model(clauses, s.model))
            else:
                unsat += 1
        self.assertEqual(sat + unsat, 6)

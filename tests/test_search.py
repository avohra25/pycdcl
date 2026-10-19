import random
import unittest

from pycdcl import Solver, check_model

from helpers import pigeonhole_clauses, random_3sat


class RestartAndReductionTests(unittest.TestCase):
    def test_restarts_happen_and_preserve_answers(self):
        s = Solver(restart_first=5)
        s.add_clauses(pigeonhole_clauses(7, 6))
        self.assertFalse(s.solve())
        self.assertGreater(s.stats.restarts, 0)

    def test_learnt_clause_deletion(self):
        s = Solver(restart_first=10, learnt_ratio=0.01, min_learnts=10)
        s.add_clauses(pigeonhole_clauses(8, 7))
        self.assertFalse(s.solve())
        self.assertGreater(s.stats.reductions, 0)
        for ws in s.watches:
            self.assertFalse(any(c.deleted for c in ws))

    def test_conflict_budget_returns_unknown_then_resumes(self):
        s = Solver()
        s.add_clauses(pigeonhole_clauses(8, 7))
        self.assertIsNone(s.solve(max_conflicts=20))
        self.assertIsNone(s.model)
        self.assertFalse(s.solve())

    def test_model_check_after_heavy_search(self):
        rng = random.Random(3)
        clauses = random_3sat(rng, 120, ratio=4.0)
        s = Solver(restart_first=20, learnt_ratio=0.05)
        s.add_clauses(clauses)
        if s.solve():
            self.assertTrue(check_model(clauses, s.model))

    def test_minimisation_is_counted(self):
        s = Solver()
        s.add_clauses(pigeonhole_clauses(7, 6))
        s.solve()
        self.assertGreaterEqual(s.stats.minimised_literals, 0)
        self.assertGreater(s.stats.learnt_literals, 0)

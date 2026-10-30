import random
import unittest

from pycdcl import Solver

from helpers import brute_force_sat, pigeonhole_clauses, random_cnf


class AssumptionCoreTests(unittest.TestCase):
    def test_simple_chain(self):
        s = Solver()
        s.add_clauses([[-1, 2], [-2, 3]])
        self.assertFalse(s.solve(assumptions=[5, 1, 6, -3]))
        self.assertEqual(sorted(s.core), [-3, 1])
        self.assertTrue(s.failed(1) and s.failed(-3))
        self.assertFalse(s.failed(5))

    def test_contradictory_assumptions(self):
        s = Solver()
        s.add_clause([1, 2])
        self.assertFalse(s.solve(assumptions=[3, -3]))
        self.assertEqual(sorted(s.core), [-3, 3])

    def test_assumption_refuted_by_formula_alone(self):
        s = Solver()
        s.add_clauses([[1], [-1, 2]])
        self.assertFalse(s.solve(assumptions=[3, -2]))
        self.assertEqual(s.core, [-2])

    def test_unsat_formula_gives_empty_core(self):
        s = Solver()
        s.add_clauses(pigeonhole_clauses(4, 3))
        # Search may stop at a failed assumption before refuting the whole
        # formula, so any subset of the assumptions is a valid answer here.
        self.assertFalse(s.solve(assumptions=[1, 2]))
        self.assertTrue(set(s.core) <= {1, 2})
        self.assertFalse(s.solve())
        self.assertEqual(s.core, [])
        self.assertFalse(s.solve(assumptions=[1, 2]))
        self.assertEqual(s.core, [])

    def test_core_cleared_on_sat_and_unknown(self):
        s = Solver()
        s.add_clause([1, 2])
        self.assertFalse(s.solve(assumptions=[-1, -2]))
        self.assertIsNotNone(s.core)
        self.assertTrue(s.solve())
        self.assertIsNone(s.core)
        p = Solver()
        p.add_clauses(pigeonhole_clauses(8, 7))
        self.assertIsNone(p.solve(max_conflicts=5))
        self.assertIsNone(p.core)

    def test_selector_core_after_search(self):
        # Pigeonhole guarded by selectors: the core must name enough of them
        # to stay unsatisfiable, and is found after real conflict analysis.
        clauses = pigeonhole_clauses(6, 5)
        n = 30
        s = Solver()
        sels = []
        for i, c in enumerate(clauses):
            sel = n + 1 + i
            sels.append(sel)
            s.add_clause(c + [-sel])
        self.assertFalse(s.solve(assumptions=sels))
        self.assertTrue(set(s.core) <= set(sels))
        kept = [clauses[sel - n - 1] for sel in s.core]
        t = Solver()
        t.add_clauses(kept)
        self.assertFalse(t.solve())
        self.assertGreater(s.stats.conflicts, 0)

    def test_random_cores_against_brute_force(self):
        rng = random.Random(53)
        checked = 0
        for _ in range(1500):
            nv = rng.randint(2, 9)
            clauses = random_cnf(rng, nv, rng.randint(1, 30))
            assumptions = [rng.choice((1, -1)) * rng.randint(1, nv)
                           for _ in range(rng.randint(1, 6))]
            s = Solver()
            s.add_clauses(clauses)
            result = s.solve(assumptions=assumptions)
            self.assertEqual(result, brute_force_sat(nv, clauses, assumptions))
            if result:
                self.assertIsNone(s.core)
                continue
            checked += 1
            self.assertTrue(set(s.core) <= set(assumptions), (clauses, assumptions, s.core))
            self.assertFalse(brute_force_sat(nv, clauses, s.core), (clauses, assumptions, s.core))
            # The solver stays usable and agrees again without assumptions.
            self.assertEqual(s.solve(), brute_force_sat(nv, clauses))
        self.assertGreater(checked, 300)


if __name__ == "__main__":
    unittest.main()

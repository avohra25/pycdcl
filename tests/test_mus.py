import itertools
import random
import unittest

from pycdcl.mus import is_mus, unsat_core

from helpers import brute_force_sat, pigeonhole_clauses, random_cnf


def brute_force_is_mus(nv, clauses, idx):
    chosen = [clauses[i] for i in idx]
    if brute_force_sat(nv, chosen):
        return False
    return all(brute_force_sat(nv, chosen[:k] + chosen[k + 1:]) for k in range(len(chosen)))


class MusTests(unittest.TestCase):
    def test_satisfiable_returns_none(self):
        self.assertIsNone(unsat_core([[1, 2], [-1, 2]]))
        self.assertIsNone(unsat_core([]))

    def test_drops_irrelevant_clauses(self):
        clauses = [[5, 6], [1], [7, -8], [-1, 2], [9], [-2]]
        self.assertEqual(unsat_core(clauses), [1, 3, 5])

    def test_empty_clause_is_its_own_mus(self):
        self.assertEqual(unsat_core([[1], [], [-1, 2]]), [1])

    def test_hard_clauses_are_never_reported(self):
        self.assertEqual(unsat_core([[3], [1], [4]], hard=[[-1]]), [1])
        self.assertEqual(unsat_core([[2]], hard=[[1], [-1]]), [])

    def test_pigeonhole_is_its_own_mus(self):
        # Every clause of a pigeonhole formula is necessary.
        clauses = pigeonhole_clauses(5, 4)
        self.assertEqual(unsat_core(clauses), list(range(len(clauses))))

    def test_pigeonhole_buried_in_noise(self):
        rng = random.Random(7)
        php = pigeonhole_clauses(5, 4)
        noise = [[rng.choice((1, -1)) * rng.randint(21, 40) for _ in range(3)] for _ in range(60)]
        clauses = php + noise
        rng.shuffle(clauses)
        core = unsat_core(clauses)
        self.assertEqual(sorted(map(sorted, (clauses[i] for i in core))), sorted(map(sorted, php)))
        self.assertTrue(is_mus(clauses, core))
        loose = unsat_core(clauses, minimal=False)
        self.assertTrue(set(core) <= set(loose))  # the MUS is carved out of the first core

    def test_random_against_brute_force(self):
        rng = random.Random(1907)
        found = 0
        for _ in range(400):
            nv = rng.randint(2, 7)
            clauses = random_cnf(rng, nv, rng.randint(1, 24))
            core = unsat_core(clauses)
            sat = brute_force_sat(nv, clauses)
            self.assertEqual(core is None, sat)
            if core is None:
                continue
            found += 1
            self.assertTrue(brute_force_is_mus(nv, clauses, core), (clauses, core))
            self.assertTrue(is_mus(clauses, core))
            loose = unsat_core(clauses, minimal=False)
            self.assertFalse(brute_force_sat(nv, [clauses[i] for i in loose]))
        self.assertGreater(found, 100)

    def test_is_mus_rejects_non_minimal_and_sat(self):
        clauses = [[1], [-1], [2], [-2]]
        self.assertTrue(is_mus(clauses, [0, 1]))
        self.assertFalse(is_mus(clauses, [0, 1, 2]))
        self.assertFalse(is_mus(clauses, [0, 2]))

    def test_every_small_unsat_formula(self):
        # All 2-variable formulas built from four distinct clauses.
        lits = [1, -1, 2, -2]
        pool = [list(c) for r in (1, 2) for c in itertools.combinations(lits, r)]
        for combo in itertools.combinations(pool, 4):
            clauses = list(combo)
            core = unsat_core(clauses)
            if core is not None:
                self.assertTrue(brute_force_is_mus(2, clauses, core), (clauses, core))


if __name__ == "__main__":
    unittest.main()

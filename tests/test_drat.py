import io
import random
import unittest

from pycdcl import Solver
from pycdcl.drat import ProofError, check_proof, parse_proof

from helpers import brute_force_sat, pigeonhole_clauses, random_3sat, random_cnf


def solve_with_proof(clauses, **kw):
    buf = io.StringIO()
    s = Solver(proof=buf, **kw)
    s.add_clauses(clauses)
    return s.solve(), buf.getvalue(), s


class ProofLoggingTests(unittest.TestCase):
    def test_pigeonhole_proofs_verify(self):
        for p, h in [(4, 3), (6, 5), (7, 6)]:
            result, proof, _ = solve_with_proof(pigeonhole_clauses(p, h))
            self.assertFalse(result)
            check = check_proof(pigeonhole_clauses(p, h), proof)
            self.assertTrue(check.verified, check.message)
            self.assertGreater(check.lemmas, 0)

    def test_proofs_with_clause_deletion_verify(self):
        clauses = pigeonhole_clauses(7, 6)
        result, proof, s = solve_with_proof(clauses, restart_first=10, learnt_ratio=0.01, min_learnts=10)
        self.assertFalse(result)
        self.assertGreater(s.stats.reductions, 0)
        check = check_proof(clauses, proof)
        self.assertTrue(check.verified, check.message)
        self.assertGreater(check.deletions, 0)

    def test_random_unsat_3sat_proofs_verify(self):
        rng = random.Random(11)
        verified = 0
        for _ in range(12):
            clauses = random_3sat(rng, 60, ratio=5.0)
            result, proof, _ = solve_with_proof(clauses)
            if result is False:
                check = check_proof(clauses, proof)
                self.assertTrue(check.verified, check.message)
                verified += 1
        self.assertGreater(verified, 5)

    def test_random_small_formulas(self):
        rng = random.Random(29)
        for _ in range(600):
            nv = rng.randint(1, 8)
            clauses = random_cnf(rng, nv, rng.randint(1, 30))
            result, proof, _ = solve_with_proof(clauses)
            self.assertEqual(result, brute_force_sat(nv, clauses))
            if result is False:
                check = check_proof(clauses, proof)
                self.assertTrue(check.verified, (clauses, proof, check.message))

    def test_trivial_refutations_log_the_empty_clause(self):
        for clauses in ([[1], [-1]], [[]], [[1, 2], [-1], [-2]]):
            result, proof, _ = solve_with_proof(clauses)
            self.assertFalse(result)
            self.assertTrue(proof.endswith("0\n"))
            self.assertTrue(check_proof(clauses, proof).verified, clauses)

    def test_satisfiable_run_does_not_prove_unsat(self):
        clauses = [[1, 2], [-1, 2], [1, -2]]
        result, proof, _ = solve_with_proof(clauses)
        self.assertTrue(result)
        self.assertFalse(check_proof(clauses, proof).verified)


class CheckerTests(unittest.TestCase):
    XOR2 = [[1, 2], [-1, 2], [1, -2], [-1, -2]]

    def test_accepts_hand_written_proof(self):
        r = check_proof(self.XOR2, "c a comment\n2 0\n0\n")
        self.assertTrue(r.verified)
        self.assertEqual(r.lemmas, 2)

    def test_conflict_after_last_lemma_counts(self):
        self.assertTrue(check_proof(self.XOR2, "2 0\n").verified)
        self.assertTrue(check_proof([[1], [-1]], "").verified)

    def test_rejects_non_rup_lemma(self):
        r = check_proof([[1, 2, 3], [-1, 2], [-2, 3]], "-3 0\n0\n")
        self.assertFalse(r.verified)
        self.assertEqual(r.failed_line, 1)
        self.assertIn("not implied", r.message)

    def test_rejects_tampered_solver_proof(self):
        clauses = pigeonhole_clauses(6, 5)
        _, proof, _ = solve_with_proof(clauses)
        lines = proof.splitlines()
        bogus = lines[:3] + ["1 0"] + lines[3:]
        self.assertFalse(check_proof(clauses, "\n".join(bogus) + "\n").verified)
        # Dropping the input clauses a proof relies on also breaks it.
        self.assertFalse(check_proof(clauses[: len(clauses) // 2], proof).verified)

    def test_truncated_proof_is_not_verified(self):
        clauses = pigeonhole_clauses(6, 5)
        _, proof, _ = solve_with_proof(clauses)
        half = "\n".join(proof.splitlines()[:10]) + "\n"
        r = check_proof(clauses, half)
        self.assertFalse(r.verified)
        self.assertIn("without deriving the empty clause", r.message)

    def test_deletions(self):
        # Deleting a clause the refutation needs makes the next lemma fail.
        r = check_proof(self.XOR2, "d 1 2 0\n2 0\n0\n")
        self.assertFalse(r.verified)
        self.assertEqual(r.deletions, 1)
        r = check_proof(self.XOR2, "d 2 1 0\n")
        self.assertFalse(r.verified)
        # Deleting a clause that is not there is an error; deleting a duplicate leaves one copy.
        self.assertIn("not in the formula", check_proof(self.XOR2, "d 1 3 0\n").message)
        self.assertTrue(check_proof(self.XOR2 + [[1, 2]], "d 1 2 0\n2 0\n0\n").verified)
        # Unit deletions are ignored, as in drat-trim.
        self.assertTrue(check_proof([[1], [-1, 2], [-2]], "d 1 0\n0\n").verified)

    def test_parse_errors(self):
        with self.assertRaises(ProofError):
            list(parse_proof("1 2\n"))
        with self.assertRaises(ProofError):
            list(parse_proof("1 x 0\n"))
        self.assertFalse(check_proof(self.XOR2, "1 0 2 0\n").verified)
        self.assertEqual(list(parse_proof("d 1 -2 0\n\nc x\n0\n")), [(1, True, [1, -2]), (4, False, [])])


if __name__ == "__main__":
    unittest.main()

import unittest

from pycdcl import DimacsError, dumps, parse


class ParseTests(unittest.TestCase):
    def test_basic(self):
        text = "c hello\np cnf 3 2\n1 -2 0\n2 3 0\n"
        self.assertEqual(parse(text), (3, [[1, -2], [2, 3]]))

    def test_clauses_span_and_share_lines(self):
        text = "p cnf 4 3\n1 2\n -3 0 4 0\n-1\n0\n"
        self.assertEqual(parse(text), (4, [[1, 2, -3], [4], [-1]]))

    def test_satlib_percent_terminator(self):
        text = "p cnf 2 1\n1 2 0\n%\n0\n\n"
        self.assertEqual(parse(text), (2, [[1, 2]]))

    def test_missing_trailing_zero(self):
        self.assertEqual(parse("p cnf 2 1\n1 -2"), (2, [[1, -2]]))

    def test_headerless_infers_vars(self):
        self.assertEqual(parse("1 -5 0\n"), (5, [[1, -5]]))

    def test_empty_clause(self):
        self.assertEqual(parse("p cnf 1 2\n1 0\n0\n"), (1, [[1], []]))

    def test_errors(self):
        for bad in ("p cnf x 1\n", "p dnf 1 1\n1 0\n", "p cnf 1 1\n2 0\n",
                    "p cnf 2 2\n1 0\n", "p cnf 1 1\n1 a 0\n", "p cnf 1 1\np cnf 1 1\n1 0\n"):
            with self.subTest(bad=bad), self.assertRaises(DimacsError):
                parse(bad)

    def test_roundtrip(self):
        clauses = [[1, -2, 3], [-1], [2, 3]]
        text = dumps(clauses, comments=["generated"])
        self.assertTrue(text.startswith("c generated\np cnf 3 3\n"))
        self.assertEqual(parse(text), (3, clauses))


if __name__ == "__main__":
    unittest.main()

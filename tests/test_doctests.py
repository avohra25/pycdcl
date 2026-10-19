import doctest

import pycdcl.solver


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(pycdcl.solver))
    return tests

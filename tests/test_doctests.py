import doctest

import pycdcl.drat
import pycdcl.mus
import pycdcl.solver


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(pycdcl.solver))
    tests.addTests(doctest.DocTestSuite(pycdcl.mus))
    tests.addTests(doctest.DocTestSuite(pycdcl.drat))
    return tests

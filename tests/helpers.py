import itertools
import random


def brute_force_sat(num_vars, clauses, assumptions=()):
    for bits in itertools.product((False, True), repeat=num_vars):
        holds = lambda l: (l > 0) == bits[abs(l) - 1]  # noqa: E731
        if all(holds(a) for a in assumptions) and all(any(holds(l) for l in c) for c in clauses):
            return True
    return False


def random_cnf(rng: random.Random, num_vars, num_clauses, width=3):
    return [
        [rng.choice((1, -1)) * rng.randint(1, num_vars) for _ in range(rng.randint(1, width))]
        for _ in range(num_clauses)
    ]


def random_3sat(rng: random.Random, num_vars, ratio=4.26):
    return [
        [rng.choice((1, -1)) * v for v in rng.sample(range(1, num_vars + 1), 3)]
        for _ in range(int(ratio * num_vars))
    ]


def pigeonhole_clauses(pigeons, holes):
    var = lambda p, h: p * holes + h + 1  # noqa: E731
    clauses = [[var(p, h) for h in range(holes)] for p in range(pigeons)]
    for h in range(holes):
        for a in range(pigeons):
            for b in range(a + 1, pigeons):
                clauses.append([-var(a, h), -var(b, h)])
    return clauses

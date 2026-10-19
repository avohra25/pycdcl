"""pycdcl: a small, readable CDCL SAT solver in pure Python."""

from .dimacs import DimacsError, dumps, load, parse
from .solver import Solver, check_model, solve

__all__ = ["Solver", "solve", "check_model", "parse", "load", "dumps", "DimacsError"]
__version__ = "0.1.0"

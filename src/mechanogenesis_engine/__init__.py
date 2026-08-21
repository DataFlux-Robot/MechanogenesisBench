"""Canonical mechanism IR and deterministic reference execution semantics."""

from .compiler import load_program, load_world, write_program
from .fixture_search import FixtureGoal, SearchResult, search_fixture
from .interpreter import ExecutionResult, ReferenceInterpreter
from .ir import MechanismProgram, WorldSpec

__all__ = [
    "ExecutionResult",
    "FixtureGoal",
    "MechanismProgram",
    "ReferenceInterpreter",
    "SearchResult",
    "WorldSpec",
    "load_program",
    "load_world",
    "search_fixture",
    "write_program",
]

__version__ = "0.2.0"

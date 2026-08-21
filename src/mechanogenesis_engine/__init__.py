"""Canonical mechanism IR and deterministic reference execution semantics."""

from .compiler import load_program, load_state, load_world, write_program, write_state
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
    "load_state",
    "load_world",
    "search_fixture",
    "write_program",
    "write_state",
]

__version__ = "0.3.0"

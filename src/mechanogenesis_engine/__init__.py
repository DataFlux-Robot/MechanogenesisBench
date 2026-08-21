"""Canonical mechanism IR and deterministic reference execution semantics."""

from .compiler import load_program, load_state, load_world, write_program, write_state
from .fixture_search import FixtureGoal, SearchResult, search_fixture
from .gtheta import (
    GThetaRun,
    GThetaRuntime,
    OpenAICompatibleProposer,
    ReferenceResearchProposer,
    ResearchRequest,
    StaticStrategyProposer,
)
from .interpreter import ExecutionResult, ReferenceInterpreter
from .ir import MechanismProgram, WorldSpec
from .research_strategy import FixtureResearchStrategy

__all__ = [
    "ExecutionResult",
    "FixtureGoal",
    "FixtureResearchStrategy",
    "GThetaRun",
    "GThetaRuntime",
    "MechanismProgram",
    "OpenAICompatibleProposer",
    "ReferenceInterpreter",
    "ReferenceResearchProposer",
    "ResearchRequest",
    "SearchResult",
    "StaticStrategyProposer",
    "WorldSpec",
    "load_program",
    "load_state",
    "load_world",
    "search_fixture",
    "write_program",
    "write_state",
]

__version__ = "0.4.0"

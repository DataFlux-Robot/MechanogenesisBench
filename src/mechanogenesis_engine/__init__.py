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
from .sovereign import (
    SovereignCertificate,
    certificate_from_execution,
    promotion_envelope,
    verify_canonical_ir_with_lean,
    verify_metrology_with_lean,
    verify_promotion_with_lean,
    verify_with_lean,
)

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
    "SovereignCertificate",
    "WorldSpec",
    "load_program",
    "load_state",
    "load_world",
    "certificate_from_execution",
    "promotion_envelope",
    "search_fixture",
    "write_program",
    "write_state",
    "verify_with_lean",
    "verify_canonical_ir_with_lean",
    "verify_metrology_with_lean",
    "verify_promotion_with_lean",
]

__version__ = "0.6.0"

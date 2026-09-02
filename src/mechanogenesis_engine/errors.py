class MechanogenesisEngineError(Exception):
    """Base exception for the canonical engine."""


class IRValidationError(MechanogenesisEngineError):
    """A canonical IR object is malformed or outside the reference fragment."""


class ExecutionError(MechanogenesisEngineError):
    """An operation cannot execute from the current canonical world state."""

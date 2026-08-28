class MechanogenesisBenchError(Exception):
    """Base exception for fail-closed benchmark errors."""


class SchemaError(MechanogenesisBenchError):
    """A task, submission or evaluation violates the standard."""


class VerificationError(MechanogenesisBenchError):
    """A submitted run cannot support its requested claim."""


class RunnerError(MechanogenesisBenchError):
    """A system or evaluator process failed."""

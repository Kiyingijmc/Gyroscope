"""Core exception hierarchy for Gyroscope."""


class GyroscopeError(Exception):
    """Base exception for all Gyroscope runtime errors."""


class ConstitutionViolationError(GyroscopeError):
    """Raised when an operation attempts to violate a Gyroscope constitutional law."""


class CausalViolationError(GyroscopeError):
    """Raised when information violates temporal causality (lookahead bias, invalid timestamp)."""


class DeterminismViolationError(GyroscopeError):
    """Raised when non-deterministic state execution or replay drift is detected."""


class StateCorruptedException(GyroscopeError):
    """Raised when serialized state hash verification fails or state is corrupted."""


class VersionMismatchError(GyroscopeError):
    """Raised when deserializing an incompatible schema or model version."""


class AuthorityViolationError(GyroscopeError):
    """Raised when a research or non-authorized component attempts execution actions."""


class InvalidConfigurationError(GyroscopeError):
    """Raised when system configuration is invalid or hash verification fails."""

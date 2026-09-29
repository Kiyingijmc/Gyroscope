"""Core domain types and enums for Gyroscope."""

from enum import Enum, unique


@unique
class ReadinessLevel(str, Enum):
    """Readiness Level classification for code, models, and features."""
    R0 = "R0"  # Unvalidated
    R1 = "R1"  # Diagnostic
    R2 = "R2"  # Research Candidate
    R3 = "R3"  # Production Candidate (Simulated Execution)
    R4 = "R4"  # Production (Live Execution Allowed)

    @property
    def is_production_executable(self) -> bool:
        return self == ReadinessLevel.R4


@unique
class LogCategory(str, Enum):
    """Structured telemetry logging categories."""
    OBSERVATION = "OBSERVATION"
    STATE_TRANSITION = "STATE_TRANSITION"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    EVIDENCE = "EVIDENCE"
    HEALTH = "HEALTH"
    EPISODE = "EPISODE"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    PERSISTENCE = "PERSISTENCE"
    RECOVERY = "RECOVERY"
    RESEARCH = "RESEARCH"
    ERROR = "ERROR"

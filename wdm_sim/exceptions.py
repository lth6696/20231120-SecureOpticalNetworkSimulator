class SimulationError(RuntimeError):
    """Base exception for simulator errors."""


class ConfigurationError(SimulationError):
    """Raised when a configuration file is invalid."""


class TopologyError(SimulationError):
    """Raised when a topology or path is invalid."""


class ResourceUnavailableError(SimulationError):
    """Raised when a physical or virtual resource cannot be reserved."""


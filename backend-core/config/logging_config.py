"""
Logging configuration using chromatrace and Lagom for dependency injection.
"""
import os

from chromatrace import LoggingConfig, LoggingSettings
from lagom import Container

# Create container for dependency injection
container = Container()

# Configure logging settings based on environment
application_level = os.environ.get("APPLICATION_LEVEL", "Development")
enable_tracing = os.environ.get("ENABLE_TRACING", "True") == "True"
enable_file_logging = os.environ.get("ENABLE_FILE_LOGGING", "True") == "True"
ignore_nan_trace = os.environ.get("IGNORE_NAN_TRACE", "False") == "True"

# Register logging settings in container
container[LoggingSettings] = LoggingSettings(
    log_level="DEBUG",
    application_level=application_level,
    enable_tracing=enable_tracing,
    ignore_nan_trace=ignore_nan_trace,
    enable_file_logging=enable_file_logging,
)

# Register logging config in container
container[LoggingConfig] = LoggingConfig(container[LoggingSettings])


def get_logger(name: str):
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__ or class name)
        
    Returns:
        Configured logger instance
    """
    logging_config = container[LoggingConfig]
    return logging_config.get_logger(name)

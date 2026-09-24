"""
Logging configuration using chromatrace and pydantic settings for dependency injection.
"""
from chromatrace import LoggingConfig, LoggingSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingEnvSettings(BaseSettings):
    """Environment-based logging configuration using pydantic settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    application_level: str = "Development"
    enable_tracing: bool = True
    enable_file_logging: bool = True
    ignore_nan_trace: bool = False


class ChromatraceLogger:
    """Singleton logger manager using chromatrace"""
    
    _instance = None
    _logging_config: LoggingConfig | None = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize chromatrace logging configuration"""
        # Load settings from environment
        env_settings = LoggingEnvSettings()
        
        # Create logging settings
        logging_settings = LoggingSettings(
            log_level="DEBUG",
            application_level=env_settings.application_level,
            enable_tracing=env_settings.enable_tracing,
            ignore_nan_trace=env_settings.ignore_nan_trace,
            enable_file_logging=env_settings.enable_file_logging,
        )
        
        # Create logging config
        self._logging_config = LoggingConfig(logging_settings)
    
    def get_logger(self, name: str):
        """
        Get a configured logger instance.
        
        Args:
            name: Logger name (typically __name__ or class name)
            
        Returns:
            Configured logger instance
            
        Example:
            >>> from infrastructure.logging import get_logger
            >>> logger = get_logger(__name__)
            >>> logger.info("Processing started")
        """
        if self._logging_config is None:
            self._initialize()
        
        return self._logging_config.get_logger(name)


# Singleton instance
_logger_manager = ChromatraceLogger()


def get_logger(name: str):
    """
    Get a configured logger instance.
    
    This is the main function to use across the application for consistent logging.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        ```python
        from infrastructure.logging import get_logger
        
        logger = get_logger(__name__)
        logger.info("Starting process")
        logger.error("Error occurred", exc_info=True)
        ```
    """
    return _logger_manager.get_logger(name)


def configure_logging(
    application_level: str | None = None,
    enable_tracing: bool | None = None,
    enable_file_logging: bool | None = None,
    ignore_nan_trace: bool | None = None
):
    """
    Reconfigure logging settings at runtime.
    
    Args:
        application_level: Application environment level
        enable_tracing: Enable trace logging
        enable_file_logging: Enable file-based logging
        ignore_nan_trace: Ignore NaN values in traces
    """
    env_settings = LoggingEnvSettings()
    
    # Override with provided values
    if application_level is not None:
        env_settings.application_level = application_level
    if enable_tracing is not None:
        env_settings.enable_tracing = enable_tracing
    if enable_file_logging is not None:
        env_settings.enable_file_logging = enable_file_logging
    if ignore_nan_trace is not None:
        env_settings.ignore_nan_trace = ignore_nan_trace
    
    # Recreate logging config
    logging_settings = LoggingSettings(
        application_level=env_settings.application_level,
        enable_tracing=env_settings.enable_tracing,
        ignore_nan_trace=env_settings.ignore_nan_trace,
        enable_file_logging=env_settings.enable_file_logging,
    )
    
    _logger_manager._logging_config = LoggingConfig(logging_settings)

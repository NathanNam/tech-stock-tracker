"""
Utility functions for the Tech Stock Tracker application.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs for better observability.
    """

    def format(self, record):
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'stock_symbol'):
            log_entry["stock_symbol"] = record.stock_symbol
        if hasattr(record, 'operation'):
            log_entry["operation"] = record.operation
        if hasattr(record, 'duration'):
            log_entry["duration_seconds"] = record.duration
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", log_file: str = None, structured: bool = False) -> logging.Logger:
    """
    Set up logging configuration with optional structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        structured: Whether to use structured JSON logging

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)

    # Configure logging format
    if structured:
        formatter = StructuredFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_formatter = formatter

    # Create handlers
    handlers = []

    # Console handler (always human-readable)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # File handler (structured if requested)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    # Get logger for this application
    logger = logging.getLogger("stock_tracker")

    return logger


def create_structured_log_record(logger: logging.Logger, level: int, message: str, **kwargs):
    """
    Create a structured log record with additional context.

    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **kwargs: Additional structured fields
    """
    record = logger.makeRecord(
        logger.name, level, __file__, 0, message, (), None
    )

    # Add structured fields
    for key, value in kwargs.items():
        setattr(record, key, value)

    logger.handle(record)


def log_stock_operation(logger: logging.Logger, operation: str, symbol: str = None,
                       duration: float = None, success: bool = True, **kwargs):
    """
    Log a stock-related operation with structured context.

    Args:
        logger: Logger instance
        operation: Operation name (e.g., 'fetch_stock', 'refresh_data')
        symbol: Stock symbol (optional)
        duration: Operation duration in seconds (optional)
        success: Whether the operation was successful
        **kwargs: Additional context fields
    """
    level = logging.INFO if success else logging.ERROR
    message = f"Stock operation: {operation}"

    context = {
        'operation': operation,
        'success': success,
        **kwargs
    }

    if symbol:
        context['stock_symbol'] = symbol
        message += f" for {symbol}"

    if duration is not None:
        context['duration'] = duration
        message += f" ({duration:.3f}s)"

    if not success:
        message += " FAILED"

    create_structured_log_record(logger, level, message, **context)


def format_currency(amount: float, precision: int = 2) -> str:
    """
    Format a number as currency.
    
    Args:
        amount: The amount to format
        precision: Number of decimal places
        
    Returns:
        Formatted currency string
    """
    if amount >= 1_000_000_000:
        return f"${amount/1_000_000_000:.{precision}f}B"
    elif amount >= 1_000_000:
        return f"${amount/1_000_000:.{precision}f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.{precision}f}K"
    else:
        return f"${amount:.{precision}f}"


def format_volume(volume: int) -> str:
    """
    Format trading volume for display.
    
    Args:
        volume: Trading volume as integer
        
    Returns:
        Formatted volume string
    """
    if volume >= 1_000_000_000:
        return f"{volume/1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        return f"{volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"{volume/1_000:.1f}K"
    else:
        return str(volume)


def validate_config():
    """
    Validate application configuration.
    
    Raises:
        ValueError: If configuration is invalid
    """
    from config import Config
    
    config = Config()
    
    # Validate symbols list
    if not config.SYMBOLS or not isinstance(config.SYMBOLS, list):
        raise ValueError("SYMBOLS must be a non-empty list")
    
    # Validate refresh interval
    if not isinstance(config.REFRESH_INTERVAL, int) or config.REFRESH_INTERVAL < 1:
        raise ValueError("REFRESH_INTERVAL must be a positive integer")
    
    # Validate precision settings
    if not isinstance(config.PRECISION, int) or config.PRECISION < 0:
        raise ValueError("PRECISION must be a non-negative integer")
    
    if not isinstance(config.VOLUME_PRECISION, int) or config.VOLUME_PRECISION < 0:
        raise ValueError("VOLUME_PRECISION must be a non-negative integer")


class ErrorHandler:
    """Handle and log application errors gracefully."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def handle_api_error(self, symbol: str, error: Exception) -> str:
        """
        Handle API-related errors.
        
        Args:
            symbol: Stock symbol that failed
            error: The exception that occurred
            
        Returns:
            User-friendly error message
        """
        error_msg = f"Failed to fetch data for {symbol}: {str(error)}"
        self.logger.error(error_msg)
        
        # Return appropriate user message based on error type
        if "timeout" in str(error).lower():
            return f"Timeout fetching {symbol} - will retry on next refresh"
        elif "network" in str(error).lower() or "connection" in str(error).lower():
            return f"Network error fetching {symbol} - check internet connection"
        elif "not found" in str(error).lower() or "invalid" in str(error).lower():
            return f"Invalid symbol {symbol} - check configuration"
        else:
            return f"Error fetching {symbol} - will retry on next refresh"
    
    def handle_display_error(self, error: Exception) -> str:
        """
        Handle display-related errors.
        
        Args:
            error: The exception that occurred
            
        Returns:
            User-friendly error message
        """
        error_msg = f"Display error: {str(error)}"
        self.logger.error(error_msg)
        
        return "Display error - please try refreshing or restart the application"
    
    def handle_general_error(self, error: Exception, context: str = "") -> str:
        """
        Handle general application errors.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            User-friendly error message
        """
        error_msg = f"General error{' in ' + context if context else ''}: {str(error)}"
        self.logger.error(error_msg, exc_info=True)
        
        return f"An error occurred{' in ' + context if context else ''}. Please try again."


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry function calls on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        import time
        from functools import wraps
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        break
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        break
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
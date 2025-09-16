"""
Utility functions for the Tech Stock Tracker application.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from opentelemetry import trace


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs with OpenTelemetry trace correlation.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add OpenTelemetry trace context if available
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            span_context = current_span.get_span_context()
            log_data.update({
                "trace_id": format(span_context.trace_id, "032x"),
                "span_id": format(span_context.span_id, "016x"),
                "trace_flags": span_context.trace_flags,
            })

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info']:
                log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging(log_level: str = "INFO", log_file: str = None, structured: bool = True) -> logging.Logger:
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
        formatter = StructuredFormatter()
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(log_format, date_format)

    # Get logger for this application and configure level/propagation
    logger = logging.getLogger("stock_tracker")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.propagate = True

    def _find_matching_handler(new_handler: logging.Handler):
        """Return an existing handler that matches the new handler, if any."""
        for existing in logger.handlers:
            if type(existing) is not type(new_handler):
                continue

            if isinstance(new_handler, logging.FileHandler):
                if getattr(existing, "baseFilename", None) == getattr(
                    new_handler, "baseFilename", None
                ):
                    return existing
            elif isinstance(new_handler, logging.StreamHandler):
                if getattr(existing, "stream", None) is getattr(
                    new_handler, "stream", None
                ):
                    return existing
        return None

    # Create handlers and attach them if not already present
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    for handler in handlers:
        handler.setFormatter(formatter)
        matching_handler = _find_matching_handler(handler)
        if matching_handler:
            matching_handler.setFormatter(formatter)
            handler.close()
        else:
            logger.addHandler(handler)

    return logger


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


def create_structured_log_entry(
    message: str,
    operation: str = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a structured log entry with common fields.

    Args:
        message: Log message
        operation: Operation being performed
        **kwargs: Additional fields to include

    Returns:
        Dictionary with structured log data
    """
    log_entry = {
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }

    if operation:
        log_entry["operation"] = operation

    # Add OpenTelemetry trace context if available
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        span_context = current_span.get_span_context()
        log_entry.update({
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
        })

    # Add any additional fields
    log_entry.update(kwargs)

    return log_entry


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
    """Handle and log application errors gracefully with structured logging."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.tracer = trace.get_tracer(__name__)

    def handle_api_error(self, symbol: str, error: Exception) -> str:
        """
        Handle API-related errors with structured logging.

        Args:
            symbol: Stock symbol that failed
            error: The exception that occurred

        Returns:
            User-friendly error message
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # Log with structured data
        self.logger.error(
            f"API error for symbol {symbol}",
            extra={
                "error_type": error_type,
                "error_message": error_msg,
                "stock_symbol": symbol,
                "operation": "api_fetch",
                "error_category": "api_error"
            },
            exc_info=True
        )

        # Return appropriate user message based on error type
        if "timeout" in error_msg.lower():
            return f"Timeout fetching {symbol} - will retry on next refresh"
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            return f"Network error fetching {symbol} - check internet connection"
        elif "not found" in error_msg.lower() or "invalid" in error_msg.lower():
            return f"Invalid symbol {symbol} - check configuration"
        else:
            return f"Error fetching {symbol} - will retry on next refresh"
    
    def handle_display_error(self, error: Exception) -> str:
        """
        Handle display-related errors with structured logging.

        Args:
            error: The exception that occurred

        Returns:
            User-friendly error message
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # Log with structured data
        self.logger.error(
            "Display error occurred",
            extra={
                "error_type": error_type,
                "error_message": error_msg,
                "operation": "display",
                "error_category": "display_error"
            },
            exc_info=True
        )

        return "Display error - please try refreshing or restart the application"

    def handle_general_error(self, error: Exception, context: str = "") -> str:
        """
        Handle general application errors with structured logging.

        Args:
            error: The exception that occurred
            context: Additional context information

        Returns:
            User-friendly error message
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # Log with structured data
        self.logger.error(
            f"General error{' in ' + context if context else ''}",
            extra={
                "error_type": error_type,
                "error_message": error_msg,
                "context": context,
                "operation": context or "general",
                "error_category": "general_error"
            },
            exc_info=True
        )

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
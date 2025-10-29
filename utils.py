"""
Utility functions for the Tech Stock Tracker application.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = None) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)
    
    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(log_file) if log_file else logging.NullHandler()
        ]
    )
    
    # Get logger for this application
    logger = logging.getLogger("stock_tracker")
    
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
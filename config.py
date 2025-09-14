"""
Configuration settings for the Tech Stock Tracker application.
"""

from typing import Dict, List


class Config:
    """Application configuration settings."""
    
    # Stock symbols to track
    SYMBOLS = [
        'GOOGL',  # Alphabet
        'AMZN',   # Amazon
        'AAPL',   # Apple
        'META',   # Meta Platforms
        'MSFT',   # Microsoft
        'NVDA',   # Nvidia
        'TSLA',   # Tesla
        'ORCL',   # Oracle
        'AVGO',   # Broadcom
    ]
    
    # Company names for display
    COMPANY_NAMES = {
        'GOOGL': 'Alphabet',
        'AMZN': 'Amazon',
        'AAPL': 'Apple',
        'META': 'Meta Platforms',
        'MSFT': 'Microsoft',
        'NVDA': 'Nvidia',
        'TSLA': 'Tesla',
        'ORCL': 'Oracle',
        'AVGO': 'Broadcom',
    }
    
    # Refresh interval in seconds
    REFRESH_INTERVAL = 60
    
    # Display settings
    PRECISION = 2  # Decimal places for prices
    VOLUME_PRECISION = 1  # Decimal places for volume (in millions)
    
    # Color settings
    POSITIVE_COLOR = "green"
    NEGATIVE_COLOR = "red"
    NEUTRAL_COLOR = "white"
    HEADER_COLOR = "cyan"
    
    # API settings
    REQUEST_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
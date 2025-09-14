"""
Stock data fetching module using yfinance.
"""

import asyncio
import yfinance as yf
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from config import Config


@dataclass
class StockInfo:
    """Data structure for stock information."""
    symbol: str
    company_name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    previous_close: Optional[float] = None


class StockDataFetcher:
    """Handles fetching stock data from yfinance API."""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.config = Config()
        self.logger = logging.getLogger(__name__)
        
    async def fetch_all_stocks(self) -> Dict[str, StockInfo]:
        """
        Fetch stock data for all symbols asynchronously.
        
        Returns:
            Dict mapping symbol to StockInfo object
        """
        # Create tasks for concurrent fetching
        tasks = [
            self._fetch_single_stock_async(symbol) 
            for symbol in self.symbols
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        stock_data = {}
        for i, result in enumerate(results):
            symbol = self.symbols[i]
            if isinstance(result, Exception):
                self.logger.error(f"Error fetching {symbol}: {result}")
                # Create placeholder data for failed requests
                stock_data[symbol] = self._create_error_stock_info(symbol)
            else:
                stock_data[symbol] = result
                
        return stock_data
    
    async def _fetch_single_stock_async(self, symbol: str) -> StockInfo:
        """
        Fetch data for a single stock symbol asynchronously.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object with current stock data
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_single_stock, symbol)
    
    def _fetch_single_stock(self, symbol: str) -> StockInfo:
        """
        Fetch data for a single stock symbol (synchronous).
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object with current stock data
            
        Raises:
            Exception: If data fetching fails
        """
        try:
            # Create yfinance Ticker object
            ticker = yf.Ticker(symbol)
            
            # Get current info
            info = ticker.info
            
            # Get historical data for price calculation
            hist = ticker.history(period="2d")
            
            if hist.empty or len(hist) < 1:
                raise ValueError(f"No historical data available for {symbol}")
            
            current_price = hist['Close'].iloc[-1]
            
            # Calculate previous close
            if len(hist) >= 2:
                previous_close = hist['Close'].iloc[-2]
            else:
                previous_close = info.get('previousClose', current_price)
            
            # Calculate change and percentage
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
            
            # Get volume (current day)
            volume = hist['Volume'].iloc[-1] if not hist.empty else info.get('volume', 0)
            
            # Get company name
            company_name = self.config.COMPANY_NAMES.get(symbol, info.get('longName', symbol))
            
            # Get market cap
            market_cap = info.get('marketCap', None)
            
            return StockInfo(
                symbol=symbol,
                company_name=company_name,
                price=float(current_price),
                change=float(change),
                change_percent=float(change_percent),
                volume=int(volume),
                market_cap=market_cap,
                previous_close=float(previous_close)
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            raise Exception(f"Failed to fetch data for {symbol}: {str(e)}")
    
    def _create_error_stock_info(self, symbol: str) -> StockInfo:
        """
        Create a placeholder StockInfo object for failed requests.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object with error/placeholder data
        """
        return StockInfo(
            symbol=symbol,
            company_name=self.config.COMPANY_NAMES.get(symbol, symbol),
            price=0.0,
            change=0.0,
            change_percent=0.0,
            volume=0,
            market_cap=None,
            previous_close=0.0
        )
    
    async def fetch_single_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """
        Fetch data for a single stock with error handling.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object or None if failed
        """
        try:
            return await self._fetch_single_stock_async(symbol)
        except Exception as e:
            self.logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def is_market_open(self) -> bool:
        """
        Check if the market is currently open.
        This is a simplified check - in production, you'd want more sophisticated logic.
        
        Returns:
            True if market appears to be open, False otherwise
        """
        now = datetime.now()
        weekday = now.weekday()  # 0 = Monday, 6 = Sunday
        hour = now.hour
        
        # Simple check: weekdays between 9:30 AM and 4:00 PM EST
        # This is approximate and doesn't account for holidays
        if weekday < 5:  # Monday to Friday
            if 9 <= hour < 16:  # 9 AM to 4 PM (approximate)
                return True
        
        return False
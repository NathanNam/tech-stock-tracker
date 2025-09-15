"""
Stock data fetching module using yfinance.
"""

import asyncio
import time
import yfinance as yf
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from config import Config
from opentelemetry import trace


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

    def __init__(self, symbols: List[str], custom_metrics: dict = None):
        self.symbols = symbols
        self.config = Config()
        self.logger = logging.getLogger(__name__)
        self.tracer = trace.get_tracer(__name__)
        self.custom_metrics = custom_metrics or {}
        
    async def fetch_all_stocks(self) -> Dict[str, StockInfo]:
        """
        Fetch stock data for all symbols asynchronously.

        Returns:
            Dict mapping symbol to StockInfo object
        """
        start_time = time.time()

        with self.tracer.start_as_current_span("fetch_all_stocks") as span:
            span.set_attribute("symbols_count", len(self.symbols))
            span.set_attribute("symbols", ",".join(self.symbols))

            # Create tasks for concurrent fetching
            tasks = [
                self._fetch_single_stock_async(symbol)
                for symbol in self.symbols
            ]

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            stock_data = {}
            successful_count = 0
            error_count = 0

            for i, result in enumerate(results):
                symbol = self.symbols[i]
                if isinstance(result, Exception):
                    error_count += 1
                    self.logger.error(f"Error fetching {symbol}: {result}")
                    # Create placeholder data for failed requests
                    stock_data[symbol] = self._create_error_stock_info(symbol)
                else:
                    successful_count += 1
                    stock_data[symbol] = result

            # Add span attributes for results
            span.set_attribute("successful_fetches", successful_count)
            span.set_attribute("failed_fetches", error_count)
            span.set_attribute("total_duration_seconds", time.time() - start_time)

            self.logger.info(f"Fetched {successful_count}/{len(self.symbols)} stocks successfully")
            return stock_data
    
    async def _fetch_single_stock_async(self, symbol: str) -> StockInfo:
        """
        Fetch data for a single stock symbol asynchronously.

        Args:
            symbol: Stock ticker symbol

        Returns:
            StockInfo object with current stock data
        """
        with self.tracer.start_as_current_span("fetch_single_stock_async") as span:
            span.set_attribute("stock_symbol", symbol)

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
        start_time = time.time()

        with self.tracer.start_as_current_span("fetch_single_stock") as span:
            span.set_attribute("stock_symbol", symbol)

            try:
                # Create yfinance Ticker object
                ticker = yf.Ticker(symbol)

                # Get current info
                with self.tracer.start_as_current_span("yfinance_get_info") as info_span:
                    info_start_time = time.time()
                    info_span.set_attribute("stock_symbol", symbol)
                    info = ticker.info

                    # Record yfinance API timing
                    if 'yfinance_api_duration' in self.custom_metrics:
                        self.custom_metrics['yfinance_api_duration'].record(
                            time.time() - info_start_time,
                            {"symbol": symbol, "api_call": "info"}
                        )

                # Get historical data for price calculation
                with self.tracer.start_as_current_span("yfinance_get_history") as hist_span:
                    hist_start_time = time.time()
                    hist_span.set_attribute("stock_symbol", symbol)
                    hist_span.set_attribute("period", "2d")
                    hist = ticker.history(period="2d")

                    # Record yfinance API timing
                    if 'yfinance_api_duration' in self.custom_metrics:
                        self.custom_metrics['yfinance_api_duration'].record(
                            time.time() - hist_start_time,
                            {"symbol": symbol, "api_call": "history"}
                        )

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

                # Add span attributes for the fetched data
                span.set_attribute("current_price", float(current_price))
                span.set_attribute("change", float(change))
                span.set_attribute("change_percent", float(change_percent))
                span.set_attribute("volume", int(volume))
                span.set_attribute("company_name", company_name)
                span.set_attribute("fetch_duration_seconds", time.time() - start_time)

                # Record success metrics
                if 'stock_data_success_total' in self.custom_metrics:
                    self.custom_metrics['stock_data_success_total'].add(1, {"symbol": symbol})

                if 'stock_price_current' in self.custom_metrics:
                    self.custom_metrics['stock_price_current'].add(
                        float(current_price),
                        {"symbol": symbol, "company": company_name}
                    )

                self.logger.info(f"Successfully fetched data for {symbol}: ${current_price:.2f} ({change_percent:+.2f}%)")

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
                # Record exception in span
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.set_attribute("fetch_duration_seconds", time.time() - start_time)

                # Record failure metrics
                if 'stock_data_failure_total' in self.custom_metrics:
                    self.custom_metrics['stock_data_failure_total'].add(1, {"symbol": symbol})

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
        with self.tracer.start_as_current_span("fetch_single_stock_info") as span:
            span.set_attribute("stock_symbol", symbol)

            try:
                result = await self._fetch_single_stock_async(symbol)
                span.set_attribute("fetch_success", True)
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.set_attribute("fetch_success", False)

                self.logger.error(f"Error fetching {symbol}: {e}")
                return None
    
    def is_market_open(self) -> bool:
        """
        Check if the market is currently open.
        This is a simplified check - in production, you'd want more sophisticated logic.

        Returns:
            True if market appears to be open, False otherwise
        """
        with self.tracer.start_as_current_span("is_market_open") as span:
            now = datetime.now()
            weekday = now.weekday()  # 0 = Monday, 6 = Sunday
            hour = now.hour

            span.set_attribute("current_weekday", weekday)
            span.set_attribute("current_hour", hour)
            span.set_attribute("current_datetime", now.isoformat())

            # Simple check: weekdays between 9:30 AM and 4:00 PM EST
            # This is approximate and doesn't account for holidays
            is_open = False
            if weekday < 5:  # Monday to Friday
                if 9 <= hour < 16:  # 9 AM to 4 PM (approximate)
                    is_open = True

            span.set_attribute("market_open", is_open)

            # Record market status metric
            if 'market_status' in self.custom_metrics:
                self.custom_metrics['market_status'].add(1 if is_open else 0)

            self.logger.info(f"Market open check: {is_open} (weekday: {weekday}, hour: {hour})")

            return is_open
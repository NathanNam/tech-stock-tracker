#!/usr/bin/env python3
"""
Tech Stock Price Tracker - Flask Web Application
A web-based application that displays real-time stock prices for major technology companies.
"""

import asyncio
import logging
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from threading import Thread
import json

from opentelemetry import trace

from stock_data import StockDataFetcher
from config import Config
from utils import setup_logging, validate_config, ErrorHandler
from otel import setup_instrumentation, create_custom_metrics

# Get the tracer for this module
tracer = trace.get_tracer(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# Initialize OpenTelemetry instrumentation
otel_logger, tracer, meter = setup_instrumentation(app, "tech-stock-tracker")
custom_metrics = create_custom_metrics(meter)

# Global variables for stock data
stock_data = {}
last_update = None
config = Config()
logger = setup_logging("INFO", "logs/stock_tracker.log", structured=True)
error_handler = ErrorHandler(logger)
data_fetcher = StockDataFetcher(config.SYMBOLS, custom_metrics)


class WebStockTracker:
    """Web-based stock tracker using Flask."""
    
    def __init__(self):
        self.running = False
        self.refresh_thread = None
        
        # Validate configuration
        try:
            validate_config()
            logger.info("Configuration validated successfully")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise
    
    async def fetch_stock_data(self):
        """Fetch stock data asynchronously."""
        global stock_data, last_update

        start_time = time.time()

        with tracer.start_as_current_span("fetch_stock_data") as span:
            try:
                logger.info("Fetching stock data...")
                otel_logger.info("Starting stock data fetch operation")

                # Record background refresh metric
                custom_metrics['background_refresh_total'].add(1)

                stock_data = await data_fetcher.fetch_all_stocks()
                last_update = datetime.now()

                # Count successful vs failed fetches
                successful = sum(1 for stock in stock_data.values() if stock.price > 0)
                total = len(stock_data)

                # Record business metrics for successful stocks
                for stock in stock_data.values():
                    if stock.price > 0:  # Only for successful fetches
                        # Record price change distribution
                        custom_metrics['stock_price_changes'].record(
                            stock.change_percent,
                            {"symbol": stock.symbol}
                        )

                        # Record volume distribution
                        volume_millions = stock.volume / 1_000_000
                        custom_metrics['stock_volumes'].record(
                            volume_millions,
                            {"symbol": stock.symbol}
                        )

                        # Record market cap distribution (if available)
                        if stock.market_cap:
                            market_cap_billions = stock.market_cap / 1_000_000_000
                            custom_metrics['market_cap_distribution'].record(
                                market_cap_billions,
                                {"symbol": stock.symbol}
                            )

                # Record timing
                duration = time.time() - start_time

                # Set span attributes
                span.set_attribute("stock.successful_count", successful)
                span.set_attribute("stock.total_count", total)
                span.set_attribute("stock.duration_seconds", duration)

                logger.info(f"Successfully fetched {successful}/{total} stocks")
                otel_logger.info(f"Stock data fetch completed: {successful}/{total} stocks in {duration:.2f}s")

                return {
                    'success': True,
                    'data': self._format_stock_data_for_web(),
                    'last_update': last_update.isoformat(),
                    'successful': successful,
                    'total': total
                }

            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                error_msg = error_handler.handle_general_error(e, "data fetching")
                logger.error(f"Error fetching stock data: {error_msg}")
                otel_logger.error(f"Stock data fetch failed: {error_msg}")

                return {
                    'success': False,
                    'error': error_msg,
                    'last_update': last_update.isoformat() if last_update else None
                }
    
    def _format_stock_data_for_web(self):
        """Format stock data for web display."""
        formatted_data = []
        
        for symbol, stock in stock_data.items():
            formatted_data.append({
                'symbol': stock.symbol,
                'company_name': stock.company_name,
                'price': stock.price,
                'change': stock.change,
                'change_percent': stock.change_percent,
                'volume': stock.volume,
                'volume_millions': stock.volume / 1_000_000,
                'is_positive': stock.change > 0,
                'is_negative': stock.change < 0,
                'market_cap': stock.market_cap
            })
        
        return formatted_data
    
    def sort_stocks(self, sort_by='name'):
        """Sort stock data by specified field."""
        if not stock_data:
            return []
        
        formatted_data = self._format_stock_data_for_web()
        
        if sort_by == 'name':
            return sorted(formatted_data, key=lambda x: x['company_name'])
        elif sort_by == 'price':
            return sorted(formatted_data, key=lambda x: x['price'], reverse=True)
        elif sort_by == 'change':
            return sorted(formatted_data, key=lambda x: x['change_percent'], reverse=True)
        else:
            return formatted_data

    def start_background_refresh(self):
        """Start background thread for periodic data refresh."""
        if not self.running:
            self.running = True
            self.refresh_thread = Thread(target=self._background_refresh_loop, daemon=True)
            self.refresh_thread.start()
            logger.info("Background refresh thread started")
    
    def _background_refresh_loop(self):
        """Background loop for refreshing data."""
        import time
        
        while self.running:
            try:
                # Run async function in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.fetch_stock_data())
                loop.close()
                
                logger.info("Background refresh completed")
                
                # Wait for next refresh
                time.sleep(config.REFRESH_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in background refresh: {e}")
                time.sleep(30)  # Wait 30 seconds before retrying


# Initialize the tracker
tracker = WebStockTracker()


@app.route('/')
def index():
    """Main page displaying stock data."""
    start_time = time.time()
    sort_by = request.args.get('sort', 'name')

    # Track concurrent requests
    custom_metrics['concurrent_requests'].add(1)

    try:
        # Record HTTP request metric
        custom_metrics['http_requests_total'].add(1, {"method": "GET", "endpoint": "/"})

        # Get sorted stock data
        stocks = tracker.sort_stocks(sort_by)

        # Record request duration
        duration = time.time() - start_time
        custom_metrics['http_request_duration'].record(duration, {"method": "GET", "endpoint": "/"})

        otel_logger.info(f"Index page accessed with sort={sort_by}, returned {len(stocks)} stocks")

        return render_template('index.html',
                             stocks=stocks,
                             last_update=last_update,
                             current_sort=sort_by,
                             config=config,
                             total_stocks=len(stocks))
    finally:
        # Decrement concurrent requests counter
        custom_metrics['concurrent_requests'].add(-1)


@app.route('/api/stocks')
def api_stocks():
    """API endpoint to get current stock data."""
    start_time = time.time()
    sort_by = request.args.get('sort', 'name')

    # Record HTTP request metric
    custom_metrics['http_requests_total'].add(1, {"method": "GET", "endpoint": "/api/stocks"})

    stocks = tracker.sort_stocks(sort_by)

    # Record request duration
    duration = time.time() - start_time
    custom_metrics['http_request_duration'].record(duration, {"method": "GET", "endpoint": "/api/stocks"})

    otel_logger.info(f"API stocks endpoint accessed with sort={sort_by}, returned {len(stocks)} stocks")

    return jsonify({
        'stocks': stocks,
        'last_update': last_update.isoformat() if last_update else None,
        'refresh_interval': config.REFRESH_INTERVAL,
        'total_stocks': len(stock_data) if stock_data else 0
    })


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """API endpoint to manually refresh stock data."""
    start_time = time.time()

    # Record HTTP request metric
    custom_metrics['http_requests_total'].add(1, {"method": "POST", "endpoint": "/api/refresh"})

    try:
        otel_logger.info("Manual refresh requested via API")

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(tracker.fetch_stock_data())
        loop.close()

        # Record request duration
        duration = time.time() - start_time
        custom_metrics['http_request_duration'].record(duration, {"method": "POST", "endpoint": "/api/refresh"})

        otel_logger.info(f"Manual refresh completed: success={result.get('success')}")

        return jsonify(result)

    except Exception as e:
        error_msg = error_handler.handle_general_error(e, "manual refresh")
        otel_logger.error(f"Manual refresh failed: {error_msg}")

        # Record request duration even for errors
        duration = time.time() - start_time
        custom_metrics['http_request_duration'].record(duration, {"method": "POST", "endpoint": "/api/refresh"})

        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


@app.route('/api/status')
def api_status():
    """API endpoint to get application status."""
    start_time = time.time()

    # Record HTTP request metric
    custom_metrics['http_requests_total'].add(1, {"method": "GET", "endpoint": "/api/status"})

    # Record request duration
    duration = time.time() - start_time
    custom_metrics['http_request_duration'].record(duration, {"method": "GET", "endpoint": "/api/status"})

    otel_logger.info("Status endpoint accessed")

    return jsonify({
        'status': 'running',
        'last_update': last_update.isoformat() if last_update else None,
        'total_stocks': len(stock_data) if stock_data else 0,
        'refresh_interval': config.REFRESH_INTERVAL,
        'background_refresh_running': tracker.running
    })


@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    otel_logger.warning(f"404 error: {error}")
    return render_template('error.html',
                         error_code=404,
                         error_message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    otel_logger.error(f"500 error: {error}")
    return render_template('error.html',
                         error_code=500,
                         error_message="Internal server error"), 500


def initialize_app():
    """Initialize the application with initial data fetch."""
    logger.info("Initializing Tech Stock Tracker web application...")
    otel_logger.info("Starting Tech Stock Tracker application initialization")

    # Fetch initial data
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(tracker.fetch_stock_data())
        loop.close()

        if result['success']:
            logger.info("Initial data fetch successful")
            otel_logger.info(f"Initial data fetch successful: {result.get('successful')}/{result.get('total')} stocks")
        else:
            logger.warning(f"Initial data fetch failed: {result.get('error')}")
            otel_logger.warning(f"Initial data fetch failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Error during initial data fetch: {e}")
        otel_logger.error(f"Error during initial data fetch: {e}")

    # Start background refresh
    tracker.start_background_refresh()
    otel_logger.info("Application initialization completed")


if __name__ == '__main__':
    # Initialize the application
    initialize_app()
    
    # Run the Flask app
    logger.info("Starting Flask development server...")
    app.run(
        debug=True,
        host='127.0.0.1',
        port=8080,
        threaded=True
    )
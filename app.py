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

from stock_data import StockDataFetcher
from config import Config
from utils import setup_logging, validate_config, ErrorHandler
from otel import setup_instrumentation, create_custom_metrics
from opentelemetry import trace

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# Set up OpenTelemetry instrumentation
otel_logger, tracer, meter = setup_instrumentation(app, "tech-stock-tracker")

# Create custom metrics
custom_metrics = create_custom_metrics(meter)

# Global variables for stock data
stock_data = {}
last_update = None
config = Config()
logger = setup_logging("INFO", "logs/stock_tracker.log")
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

        # Start timing for metrics
        start_time = time.time()

        with tracer.start_as_current_span("fetch_stock_data") as span:
            try:
                span.set_attribute("operation", "fetch_all_stocks")
                span.set_attribute("symbols_count", len(config.SYMBOLS))

                otel_logger.info("Fetching stock data...")
                stock_data = await data_fetcher.fetch_all_stocks()
                last_update = datetime.now()

                # Count successful vs failed fetches
                successful = sum(1 for stock in stock_data.values() if stock.price > 0)
                total = len(stock_data)

                # Record metrics
                custom_metrics['stock_fetches_total'].add(1, {"status": "success"})
                custom_metrics['stock_fetch_duration'].record(
                    time.time() - start_time,
                    {"status": "success"}
                )

                # Add span attributes
                span.set_attribute("stocks_successful", successful)
                span.set_attribute("stocks_total", total)
                span.set_attribute("fetch_duration_seconds", time.time() - start_time)

                otel_logger.info(f"Successfully fetched {successful}/{total} stocks")

                return {
                    'success': True,
                    'data': self._format_stock_data_for_web(),
                    'last_update': last_update.isoformat(),
                    'successful': successful,
                    'total': total
                }

            except Exception as e:
                # Record error metrics
                custom_metrics['stock_fetches_total'].add(1, {"status": "error"})
                custom_metrics['errors_total'].add(1, {"operation": "fetch_stock_data"})
                custom_metrics['stock_fetch_duration'].record(
                    time.time() - start_time,
                    {"status": "error"}
                )

                # Record exception in span
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                error_msg = error_handler.handle_general_error(e, "data fetching")
                otel_logger.error(f"Error fetching stock data: {error_msg}")
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

            # Record background task start
            custom_metrics['background_tasks_active'].add(1)
            otel_logger.info("Background refresh thread started")
    
    def _background_refresh_loop(self):
        """Background loop for refreshing data."""
        import time

        while self.running:
            with tracer.start_as_current_span("background_refresh_cycle") as span:
                try:
                    span.set_attribute("refresh_interval", config.REFRESH_INTERVAL)

                    # Run async function in thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.fetch_stock_data())
                    loop.close()

                    otel_logger.info("Background refresh completed")

                    # Wait for next refresh
                    time.sleep(config.REFRESH_INTERVAL)

                except Exception as e:
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    custom_metrics['errors_total'].add(1, {"operation": "background_refresh"})

                    otel_logger.error(f"Error in background refresh: {e}")
                    time.sleep(30)  # Wait 30 seconds before retrying


# Initialize the tracker
tracker = WebStockTracker()


@app.route('/')
def index():
    """Main page displaying stock data."""
    start_time = time.time()

    with tracer.start_as_current_span("index_page") as span:
        sort_by = request.args.get('sort', 'name')
        span.set_attribute("sort_by", sort_by)

        # Get sorted stock data
        stocks = tracker.sort_stocks(sort_by)

        # Record metrics
        custom_metrics['api_requests_total'].add(1, {"endpoint": "/", "method": "GET"})
        custom_metrics['http_request_duration'].record(
            time.time() - start_time,
            {"endpoint": "/", "method": "GET"}
        )

        span.set_attribute("stocks_count", len(stocks))
        otel_logger.info(f"Index page rendered with {len(stocks)} stocks, sorted by {sort_by}")

        return render_template('index.html',
                             stocks=stocks,
                             last_update=last_update,
                             current_sort=sort_by,
                             config=config,
                             total_stocks=len(stocks))


@app.route('/api/stocks')
def api_stocks():
    """API endpoint to get current stock data."""
    start_time = time.time()

    with tracer.start_as_current_span("api_stocks") as span:
        sort_by = request.args.get('sort', 'name')
        span.set_attribute("sort_by", sort_by)

        stocks = tracker.sort_stocks(sort_by)

        # Record metrics
        custom_metrics['api_requests_total'].add(1, {"endpoint": "/api/stocks", "method": "GET"})
        custom_metrics['http_request_duration'].record(
            time.time() - start_time,
            {"endpoint": "/api/stocks", "method": "GET"}
        )

        span.set_attribute("stocks_count", len(stocks))
        otel_logger.info(f"API stocks endpoint called, returned {len(stocks)} stocks")

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

    with tracer.start_as_current_span("api_refresh") as span:
        try:
            span.set_attribute("operation", "manual_refresh")

            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(tracker.fetch_stock_data())
            loop.close()

            # Record metrics
            custom_metrics['api_requests_total'].add(1, {"endpoint": "/api/refresh", "method": "POST"})
            custom_metrics['http_request_duration'].record(
                time.time() - start_time,
                {"endpoint": "/api/refresh", "method": "POST"}
            )

            span.set_attribute("refresh_success", result.get('success', False))
            otel_logger.info(f"Manual refresh completed: {result.get('success', False)}")

            return jsonify(result)

        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            custom_metrics['errors_total'].add(1, {"operation": "api_refresh"})

            error_msg = error_handler.handle_general_error(e, "manual refresh")
            otel_logger.error(f"Manual refresh failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500


@app.route('/api/status')
def api_status():
    """API endpoint to get application status."""
    start_time = time.time()

    with tracer.start_as_current_span("api_status") as span:
        # Record metrics
        custom_metrics['api_requests_total'].add(1, {"endpoint": "/api/status", "method": "GET"})
        custom_metrics['http_request_duration'].record(
            time.time() - start_time,
            {"endpoint": "/api/status", "method": "GET"}
        )

        status_data = {
            'status': 'running',
            'last_update': last_update.isoformat() if last_update else None,
            'total_stocks': len(stock_data) if stock_data else 0,
            'refresh_interval': config.REFRESH_INTERVAL,
            'background_refresh_running': tracker.running
        }

        span.set_attribute("total_stocks", status_data['total_stocks'])
        span.set_attribute("background_refresh_running", status_data['background_refresh_running'])

        otel_logger.info("Status endpoint called")
        return jsonify(status_data)


@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    custom_metrics['errors_total'].add(1, {"error_code": "404"})
    otel_logger.warning(f"404 error: {request.url}")
    return render_template('error.html',
                         error_code=404,
                         error_message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    custom_metrics['errors_total'].add(1, {"error_code": "500"})
    otel_logger.error(f"500 error: {error}")
    return render_template('error.html',
                         error_code=500,
                         error_message="Internal server error"), 500


def initialize_app():
    """Initialize the application with initial data fetch."""
    with tracer.start_as_current_span("initialize_app") as span:
        otel_logger.info("Initializing Tech Stock Tracker web application...")

        # Fetch initial data
        try:
            span.set_attribute("operation", "initial_data_fetch")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(tracker.fetch_stock_data())
            loop.close()

            if result['success']:
                span.set_attribute("initial_fetch_success", True)
                otel_logger.info("Initial data fetch successful")
            else:
                span.set_attribute("initial_fetch_success", False)
                otel_logger.warning(f"Initial data fetch failed: {result.get('error')}")

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            custom_metrics['errors_total'].add(1, {"operation": "initialize_app"})
            otel_logger.error(f"Error during initial data fetch: {e}")

        # Start background refresh
        tracker.start_background_refresh()
        otel_logger.info("Application initialization completed")


if __name__ == '__main__':
    # Initialize the application
    initialize_app()

    # Run the Flask app
    otel_logger.info("Starting Flask development server...")
    app.run(
        debug=True,
        host='127.0.0.1',
        port=8080,
        threaded=True
    )
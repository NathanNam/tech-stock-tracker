"""
OpenTelemetry instrumentation setup for Flask applications.

This module provides comprehensive OpenTelemetry setup including:
- Distributed tracing with OTLP HTTP exporter
- Metrics collection with Prometheus-compatible exporters
- Structured logging with trace correlation
- Automatic Flask instrumentation
"""

import logging
import os
from typing import Tuple

from flask import Flask
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _create_otlp_headers(
    target_package: str, bearer_token: str = None
) -> dict:
    """
    Create OTLP headers with authentication and target package.

    Args:
        target_package: The target package for x-observe-target-package header.
        bearer_token: Optional bearer token for authentication.

    Returns:
        Dictionary of headers for OTLP exporters.
    """
    headers = {"x-observe-target-package": target_package}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def setup_tracing(
    resource: Resource, otlp_endpoint: str, bearer_token: str = None
) -> trace.Tracer:
    """
    Set up OpenTelemetry tracing with OTLP HTTP exporter.

    Args:
        resource: OpenTelemetry resource with service attributes.
        otlp_endpoint: Endpoint for the OTLP trace exporter.
        bearer_token: Bearer token for authentication.

    Returns:
        An OpenTelemetry Tracer instance.
    """
    headers = _create_otlp_headers("Tracing", bearer_token)

    trace_provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{otlp_endpoint}/v1/traces", headers=headers
    )
    otlp_processor = BatchSpanProcessor(otlp_exporter)
    trace_provider.add_span_processor(otlp_processor)
    trace.set_tracer_provider(trace_provider)
    return trace.get_tracer(__name__)


def setup_metrics(
    resource: Resource, otlp_endpoint: str, bearer_token: str = None
) -> metrics.Meter:
    """
    Set up OpenTelemetry metrics with OTLP HTTP exporter.

    Args:
        resource: OpenTelemetry resource with service attributes.
        otlp_endpoint: Endpoint for the OTLP metric exporter.
        bearer_token: Bearer token for authentication.

    Returns:
        An OpenTelemetry Meter instance.
    """
    headers = _create_otlp_headers("Metrics", bearer_token)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{otlp_endpoint}/v1/metrics", headers=headers
        )
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[metric_reader])
    )
    return metrics.get_meter(__name__)


def setup_logging(
    resource: Resource, otlp_endpoint: str, bearer_token: str = None
) -> logging.Logger:
    """
    Set up OpenTelemetry logging with OTLP HTTP exporter.

    Args:
        resource: OpenTelemetry resource with service attributes.
        otlp_endpoint: Endpoint for the OTLP log exporter.
        bearer_token: Bearer token for authentication.

    Returns:
        A configured root logger.
    """
    headers = _create_otlp_headers("Logs", bearer_token)

    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=f"{otlp_endpoint}/v1/logs", headers=headers
            )
        )
    )

    handler = LoggingHandler(
        level=logging.NOTSET, logger_provider=logger_provider
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    LoggingInstrumentor().instrument(set_logging_format=True)

    return logging.getLogger(__name__)


def setup_instrumentation(
    app: Flask, service_name: str
) -> Tuple[logging.Logger, trace.Tracer, metrics.Meter]:
    """
    Instrument a Flask application with OpenTelemetry.

    This function sets up comprehensive observability for a Flask application including:
    - Automatic HTTP request/response tracing
    - Structured logging with trace correlation
    - Custom metrics capability
    - OTLP export to observability backends

    Args:
        app: The Flask application instance to instrument.
        service_name: Logical service name for resource attributes.

    Returns:
        Tuple containing (logger, tracer, meter) instances for custom instrumentation.
    """
    # Instrument Flask application for automatic HTTP tracing
    FlaskInstrumentor().instrument_app(app)

    # Create resource with service identification
    resource = Resource(attributes={SERVICE_NAME: service_name})
    
    # Get configuration from environment variables
    otlp_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
    )
    bearer_token = os.environ.get("OTEL_EXPORTER_OTLP_BEARER_TOKEN")

    # Set up tracing, metrics, and logging
    tracer = setup_tracing(resource, otlp_endpoint, bearer_token)
    meter = setup_metrics(resource, otlp_endpoint, bearer_token)
    logger = setup_logging(resource, otlp_endpoint, bearer_token)

    return logger, tracer, meter


def create_custom_metrics(meter: metrics.Meter) -> dict:
    """
    Create custom metrics for the stock tracker application.
    
    Args:
        meter: OpenTelemetry meter instance
        
    Returns:
        Dictionary of metric instruments
    """
    return {
        # Counter for total API requests
        'api_requests_total': meter.create_counter(
            name="api_requests_total",
            description="Total number of API requests",
            unit="1"
        ),
        
        # Counter for stock fetch operations
        'stock_fetches_total': meter.create_counter(
            name="stock_fetches_total", 
            description="Total number of stock fetch operations",
            unit="1"
        ),
        
        # Histogram for stock fetch duration
        'stock_fetch_duration': meter.create_histogram(
            name="stock_fetch_duration_seconds",
            description="Duration of stock fetch operations",
            unit="s"
        ),
        
        # Counter for errors
        'errors_total': meter.create_counter(
            name="errors_total",
            description="Total number of errors",
            unit="1"
        ),
        
        # Gauge for active background tasks
        'background_tasks_active': meter.create_up_down_counter(
            name="background_tasks_active",
            description="Number of active background tasks",
            unit="1"
        ),
        
        # Histogram for HTTP request duration
        'http_request_duration': meter.create_histogram(
            name="http_request_duration_seconds",
            description="Duration of HTTP requests",
            unit="s"
        ),

        # Up-down counter for current stock prices (for monitoring)
        'stock_price_current': meter.create_up_down_counter(
            name="stock_price_current_usd",
            description="Current stock price in USD",
            unit="USD"
        ),

        # Counter for successful stock data retrievals per symbol
        'stock_data_success_total': meter.create_counter(
            name="stock_data_success_total",
            description="Total successful stock data retrievals by symbol",
            unit="1"
        ),

        # Counter for failed stock data retrievals per symbol
        'stock_data_failure_total': meter.create_counter(
            name="stock_data_failure_total",
            description="Total failed stock data retrievals by symbol",
            unit="1"
        ),

        # Histogram for yfinance API response times
        'yfinance_api_duration': meter.create_histogram(
            name="yfinance_api_duration_seconds",
            description="Duration of yfinance API calls",
            unit="s"
        ),

        # Gauge for market status
        'market_status': meter.create_up_down_counter(
            name="market_status",
            description="Market open status (1=open, 0=closed)",
            unit="1"
        )
    }

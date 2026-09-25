"""Synthetic-only workload and bounded webhook sink for the M1 local lab."""

import json
import logging
import os
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, StatusCode

SERVICE = os.getenv("OTEL_SERVICE_NAME", "checkout")
DOWNSTREAM = os.getenv("DOWNSTREAM", "")
EVENTS = deque(maxlen=100)
EVENT_LOCK = threading.Lock()


def instrument():
    resource = Resource.create({"service.name": SERVICE, "service.namespace": "p001"})
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(), schedule_delay_millis=500))
    trace.set_tracer_provider(tp)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[
        PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=2000)
    ], views=[View(instrument_name="p001_request_duration", aggregation=ExplicitBucketHistogramAggregation(
        boundaries=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
    ))]))
    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(), schedule_delay_millis=500))
    logger = logging.getLogger("p001.workload")
    logger.setLevel(logging.INFO)
    logger.addHandler(LoggingHandler(logger_provider=lp))
    meter = metrics.get_meter("p001.workload")
    return (trace.get_tracer("p001.workload"), logger,
            meter.create_counter("p001_requests"),
            meter.create_histogram("p001_request_duration", unit="s"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log request headers, addresses, or raw payloads.

    def reply(self, code, value):
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self.reply(200, {"status": "ok"})
        if SERVICE == "webhook":
            if self.path != "/events":
                return self.reply(404, {"error": "not_found"})
            with EVENT_LOCK:
                return self.reply(200, {"events": list(EVENTS)})
        if self.path != "/work":
            return self.reply(404, {"error": "not_found"})
        started = time.monotonic()
        status = 200
        with TRACER.start_as_current_span("GET /work", context=extract({k.lower(): v for k, v in self.headers.items()}),
                                          kind=SpanKind.SERVER) as span:
            if DOWNSTREAM:
                with TRACER.start_as_current_span("dependency /work", kind=SpanKind.CLIENT):
                    headers = {}
                    inject(headers)
                    try:
                        response = requests.get(DOWNSTREAM + "/work", headers=headers, timeout=3)
                        response.raise_for_status()
                    except requests.RequestException:
                        status = 502
                        span.set_status(StatusCode.ERROR)
            trace_id = format(span.get_span_context().trace_id, "032x")
            attrs = {"service": SERVICE, "status": str(status), "route": "/work"}
            REQUESTS.add(1, attrs)
            DURATION.record(time.monotonic() - started, attrs)
            # Only generated identifiers and fixed fields enter telemetry.
            LOGGER.info("synthetic_request trace_id=%s service=%s status=%s", trace_id, SERVICE, status)
            return self.reply(status, {"service": SERVICE, "trace_id": trace_id})

    def do_POST(self):
        if SERVICE != "webhook" or self.path != "/alerts":
            return self.reply(404, {"error": "not_found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                return self.reply(413, {"error": "size_limit"})
            payload = json.loads(self.rfile.read(length))
            alerts = payload["alerts"]
            if not isinstance(alerts, list) or len(alerts) > 100:
                raise ValueError("invalid alerts")
            sanitized = []
            for alert in alerts:
                labels = alert["labels"]
                if not isinstance(labels, dict):
                    raise ValueError("invalid labels")
                sanitized.append({
                    "status": str(alert.get("status", "unknown"))[:16],
                    "labels": {key: str(labels[key])[:128] for key in
                               ("alertname", "project", "severity") if key in labels}
                })
            with EVENT_LOCK:
                EVENTS.extend(sanitized)
            self.reply(200, {"accepted": len(sanitized)})
        except (ValueError, KeyError, TypeError):
            self.reply(400, {"error": "invalid_payload"})


def traffic():
    # One request every two seconds, bounded request timeout; deployment owns lifecycle.
    while True:
        try:
            requests.get("http://checkout:8080/work", timeout=10)
        except requests.RequestException:
            pass
        time.sleep(2)


if __name__ == "__main__":
    if "--traffic" in sys.argv:
        traffic()
    else:
        if SERVICE != "webhook":
            TRACER, LOGGER, REQUESTS, DURATION = instrument()
        ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

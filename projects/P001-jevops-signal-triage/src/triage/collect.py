"""Bounded, read-only backend queries through the owned local Kubernetes API."""

import json
import os
import selectors
import subprocess
import time
from urllib.parse import urlencode

from .contracts import MAX_INPUT_BYTES, MAX_LOGS, MAX_TRACES, validate_window

QUERY_TIMEOUT = 4
RESPONSE_LIMIT = MAX_INPUT_BYTES // 3 - 1024


class OversizeError(ValueError):
    pass


def read_process(argv, timeout=QUERY_TIMEOUT, limit=RESPONSE_LIMIT):
    """A wall-clock deadline and streaming byte cap, not just a socket timeout."""
    if not 0 < timeout <= 10 or not 0 < limit <= RESPONSE_LIMIT:
        raise ValueError("invalid query bounds")
    deadline = time.monotonic() + timeout
    chunks, size = [], 0
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError("backend deadline exceeded")
                    chunk = os.read(proc.stdout.fileno(), min(65536, limit + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise OversizeError("backend response limit exceeded")
                    chunks.append(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("backend deadline exceeded")
            try:
                code = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise TimeoutError("backend deadline exceeded") from None
            if code:
                raise OSError("backend process failed")
            return json.loads(b"".join(chunks))
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()


def query_paths(start, end):
    validate_window(start, end)
    queries = {
        "metrics": ("prometheus", 9090, "/api/v1/query_range", {
            "query": '{__name__=~"p001_requests_total|p001_request_duration_seconds_sum|p001_request_duration_seconds_count"}',
            "start": start, "end": end, "step": 5, "timeout": "3s"}),
        "logs": ("loki", 3100, "/loki/api/v1/query_range", {
            "query": '{service_namespace="p001"}', "start": int(start * 1e9), "end": int(end * 1e9),
            "limit": MAX_LOGS, "direction": "forward"}),
        "traces": ("tempo", 3200, "/api/search", {"start": int(start), "end": int(end), "limit": MAX_TRACES}),
    }
    return {name: f"/api/v1/namespaces/p001/services/http:{svc}:{port}/proxy{path}?" + urlencode(params)
            for name, (svc, port, path, params) in queries.items()}


def collect(start, end, fetch):
    snapshot, timings = {}, {}
    for name, path in query_paths(start, end).items():
        before = time.perf_counter()
        try:
            snapshot[name] = {"ok": True, "data": fetch(path)}
        except TimeoutError:
            snapshot[name] = {"ok": False, "status": "timeout"}
        except OversizeError:
            snapshot[name] = {"ok": False, "status": "oversize"}
        except (OSError, ValueError, subprocess.SubprocessError):
            snapshot[name] = {"ok": False, "status": "error"}
        timings[name] = round((time.perf_counter() - before) * 1000, 3)
    return snapshot, timings

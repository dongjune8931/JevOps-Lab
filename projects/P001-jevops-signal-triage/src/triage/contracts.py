"""Closed state contract; no arbitrary strings cross the evidence boundary."""

import json
import math

SERVICES = ("checkout", "catalog", "inventory")
BACKENDS = ("metrics", "logs", "traces")
MAX_INPUT_BYTES = 1024 * 1024
MAX_STATE_BYTES = 8192
MAX_WINDOW_SECONDS = 300
MAX_ROWS = 128
MAX_POINTS = 128
MAX_LOGS = 100
MAX_TRACES = 20
SCHEMA_VERSION = "p001-state-v1"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def obj(fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def enum(*values):
    return {"enum": list(values)}


def number(maximum=1e12, nullable=False):
    return {"type": ["number", "null"] if nullable else "number", "minimum": 0, "maximum": maximum}


def array(items, maximum):
    return {"type": "array", "items": items, "maxItems": maximum}


SCHEMA = obj({
    "schema_version": enum(SCHEMA_VERSION),
    "window": obj({"start_unix": number(1e10), "end_unix": number(1e10)}),
    "services": array(obj({
        "name": enum(*SERVICES),
        "metrics": obj({
            "observed_requests": number(nullable=True),
            "request_rate_per_second": number(nullable=True),
            "error_rate": number(1, nullable=True),
            "mean_latency_ms": number(1e9, nullable=True),
            "counter_resets": number(),
            "sample_coverage": number(1),
        }),
        "logs": obj({"sample_count": number(), "error_count": number(),
                     "unrecognized_count": number(),
                     "patterns": array(obj({"template": enum("request_ok", "request_error", "unrecognized"),
                                            "count": number()}), 3)}),
        "traces": obj({"sample_count": number(), "mean_duration_ms": number(1e9, nullable=True),
                       "max_duration_ms": number(1e9, nullable=True)}),
    }), 3),
    "data_quality": obj({
        "backend_status": obj({b: enum("ok", "missing", "timeout", "error", "invalid", "oversize") for b in BACKENDS}),
        "missing_signals": array(enum(*BACKENDS, "kubernetes", "changes", "resource_usage", "dependency_spans"), 7),
        "truncated_signals": array(enum(*BACKENDS), 3),
        "invalid_signals": array(enum(*BACKENDS), 3),
        "limitations": array(enum("counter_delta_lower_bound", "logs_sampled", "trace_search_sampled",
                                  "trace_roots_only", "no_causal_labels"), 5),
    }),
})
SCHEMA["$schema"] = "https://json-schema.org/draft/2020-12/schema"
SCHEMA["title"] = SCHEMA_VERSION


def _validate(value, spec):
    # Implements only the keywords used above; no external dependency or schema fetching.
    if "enum" in spec:
        if value not in spec["enum"] or not isinstance(value, str):
            raise ValueError("invalid enum")
        return
    kind = spec["type"]
    if isinstance(kind, list):
        if value is None and "null" in kind:
            return
        kind = "number"
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(spec["required"]):
            raise ValueError("invalid object fields")
        for key, child in spec["properties"].items():
            _validate(value[key], child)
    elif kind == "array":
        if not isinstance(value, list) or len(value) > spec["maxItems"]:
            raise ValueError("invalid array")
        for item in value:
            _validate(item, spec["items"])
    elif kind == "number":
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not spec["minimum"] <= value <= spec["maximum"]):
            raise ValueError("invalid finite number")
    else:
        raise ValueError("unsupported schema keyword")


def validate_window(start, end):
    if (type(start) not in (int, float) or type(end) not in (int, float)
            or not math.isfinite(start) or not math.isfinite(end)
            or not 0 <= start < end <= 1e10 or end - start > MAX_WINDOW_SECONDS):
        raise ValueError("window must be finite, positive, and at most 300 seconds")


def validate_state(state, byte_limit=MAX_STATE_BYTES):
    if not 1024 <= byte_limit <= MAX_STATE_BYTES:
        raise ValueError("invalid state byte limit")
    _validate(state, SCHEMA)
    validate_window(state["window"]["start_unix"], state["window"]["end_unix"])
    if [s["name"] for s in state["services"]] != list(SERVICES):
        raise ValueError("services must use the canonical order")
    if len(encoded(state)) > byte_limit:
        raise ValueError("state byte limit exceeded")
    return state

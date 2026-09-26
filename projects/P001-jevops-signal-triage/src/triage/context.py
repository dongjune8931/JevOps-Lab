"""Normalize bounded raw backend snapshots; never accept ground truth labels."""

import math
import re

from .contracts import (BACKENDS, MAX_INPUT_BYTES, MAX_LOGS, MAX_POINTS, MAX_ROWS,
                        MAX_STATE_BYTES, MAX_TRACES, SCHEMA_VERSION, SERVICES,
                        encoded, validate_state, validate_window)

METRICS = ("p001_requests_total", "p001_request_duration_seconds_sum",
           "p001_request_duration_seconds_count")
LOG = re.compile(r"synthetic_request trace_id=[0-9a-f]{32} service=(checkout|catalog|inventory) status=(200|502)", re.ASCII)


def finite(value, maximum=1e12):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("invalid number")
    n = float(value)
    if not math.isfinite(n) or not 0 <= n <= maximum:
        raise ValueError("invalid number")
    return n


def rounded(n):
    return round(n, 6) if n is not None else None


def empty_service(name):
    return {"name": name, "metrics": {"observed_requests": None, "request_rate_per_second": None,
            "error_rate": None, "mean_latency_ms": None, "counter_resets": 0, "sample_coverage": 0},
            "logs": {"sample_count": 0, "error_count": 0, "unrecognized_count": 0, "patterns": []},
            "traces": {"sample_count": 0, "mean_duration_ms": None, "max_duration_ms": None}}


def matrix(data):
    if data.get("status") != "success" or data.get("data", {}).get("resultType") != "matrix":
        raise ValueError("not a successful matrix")
    return data["data"]["result"]


def rows_bounded(rows, limit, quality, backend):
    if not isinstance(rows, list):
        raise ValueError("invalid rows")
    if len(rows) > limit:
        quality["truncated_signals"].add(backend)
    # Stable for an identical fixture, independent of dict insertion order.
    return sorted(rows, key=encoded)[:limit]


def metric_summary(data, start, end, services, quality):
    aggregates = {s: {m: [] for m in METRICS} for s in SERVICES}
    seen = set()
    for row in rows_bounded(matrix(data), MAX_ROWS, quality, "metrics"):
        labels = row["metric"]
        name, service = labels.get("__name__"), labels.get("service")
        if name not in METRICS or service not in SERVICES:
            continue
        if labels.get("route") != "/work" or labels.get("status") not in ("200", "502"):
            quality["invalid_signals"].add("metrics")
            continue
        identity = encoded(labels)
        if identity in seen:
            raise ValueError("duplicate series")
        seen.add(identity)
        raw = row["values"]
        if not isinstance(raw, list):
            raise ValueError("invalid samples")
        if len(raw) > MAX_POINTS:
            quality["truncated_signals"].add("metrics")
            continue  # Never calculate a deceptively complete delta from truncated counters.
        points = {}
        try:
            for pair in raw:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("invalid point")
                t = finite(pair[0], 1e10)
                if start <= t <= end:
                    n = finite(pair[1])
                    if t in points and points[t] != n:
                        raise ValueError("conflicting sample")
                    points[t] = n
        except (ValueError, TypeError):
            quality["invalid_signals"].add("metrics")
            continue
        if len(points) < 2:
            quality["invalid_signals"].add("metrics")
            continue
        sequence = sorted(points.items())
        delta = resets = 0
        for (_, a), (_, b) in zip(sequence, sequence[1:]):
            delta += b - a if b >= a else b
            resets += int(b < a)
        coverage = (sequence[-1][0] - sequence[0][0]) / (end - start)
        aggregates[service][name].append((delta, labels["status"], resets, coverage))
    for service in SERVICES:
        fields = aggregates[service]
        requests = fields[METRICS[0]]
        sums, counts = fields[METRICS[1]], fields[METRICS[2]]
        target = services[service]["metrics"]
        all_rows = requests + sums + counts
        target["counter_resets"] = sum(r[2] for r in all_rows)
        if requests:
            total = sum(r[0] for r in requests)
            target["observed_requests"] = rounded(total)
            target["request_rate_per_second"] = rounded(total / (end - start))
            target["error_rate"] = rounded(sum(r[0] for r in requests if r[1] == "502") / total) if total else None
        if sums and counts and sum(r[0] for r in counts) > 0:
            target["mean_latency_ms"] = rounded(1000 * sum(r[0] for r in sums) / sum(r[0] for r in counts))
        if requests and sums and counts:
            target["sample_coverage"] = rounded(min(r[3] for r in all_rows))


def log_summary(data, start, end, services, quality):
    if data.get("status") != "success" or data.get("data", {}).get("resultType") != "streams":
        raise ValueError("not successful log streams")
    entries = []
    for row in rows_bounded(data["data"]["result"], MAX_ROWS, quality, "logs"):
        labels = row["stream"]
        service = labels.get("service_name")
        if service not in SERVICES or labels.get("service_namespace") != "p001":
            continue
        for pair in rows_bounded(row["values"], MAX_LOGS, quality, "logs"):
            if not isinstance(pair, list) or len(pair) < 2:
                raise ValueError("invalid log pair")
            timestamp = finite(pair[0], 1e20) / 1e9
            if start <= timestamp <= end:
                entries.append((timestamp, service, pair[1]))
    if len(entries) >= MAX_LOGS:
        quality["truncated_signals"].add("logs")  # Backend limit reached: completeness is unknown.
    counts = {s: {p: 0 for p in ("request_ok", "request_error", "unrecognized")} for s in SERVICES}
    for _, service, line in sorted(entries, key=encoded)[:MAX_LOGS]:
        # Unbounded/unknown text is never returned, truncated into state, or hashed into identifiers.
        match = LOG.fullmatch(line) if isinstance(line, str) and len(line) <= 160 else None
        pattern = ("request_ok" if match[2] == "200" else "request_error") if match and match[1] == service else "unrecognized"
        counts[service][pattern] += 1
    for service, groups in counts.items():
        services[service]["logs"] = {"sample_count": sum(groups.values()), "error_count": groups["request_error"],
                                     "unrecognized_count": groups["unrecognized"],
                                     "patterns": [{"template": k, "count": v} for k, v in sorted(groups.items()) if v]}


def trace_summary(data, start, end, services, quality):
    raw = data["traces"]
    if not isinstance(raw, list):
        raise ValueError("invalid traces")
    if len(raw) >= MAX_TRACES:
        quality["truncated_signals"].add("traces")
    durations = {s: [] for s in SERVICES}
    seen = set()
    for row in rows_bounded(raw, MAX_TRACES, quality, "traces"):
        service = row.get("rootServiceName")
        if service not in SERVICES or row.get("rootTraceName") != "GET /work":
            continue
        trace_id = row["traceID"]
        if not isinstance(trace_id, str) or not re.fullmatch("[0-9a-f]{1,32}", trace_id):
            quality["invalid_signals"].add("traces")
            continue
        trace_id = trace_id.zfill(32)  # Tempo search may return unpadded hexadecimal IDs.
        if trace_id in seen:
            continue
        seen.add(trace_id)
        try:
            if start <= finite(row["startTimeUnixNano"], 1e20) / 1e9 <= end:
                durations[service].append(finite(row["durationMs"], 1e9))
        except (KeyError, ValueError, TypeError):
            # Missing duration is not proof of zero latency; retain other valid rows.
            quality["invalid_signals"].add("traces")
    for service, values in durations.items():
        services[service]["traces"] = {"sample_count": len(values),
            "mean_duration_ms": rounded(sum(values) / len(values)) if values else None,
            "max_duration_ms": rounded(max(values)) if values else None}


def build_state(snapshot, start, end, byte_limit=MAX_STATE_BYTES):
    validate_window(start, end)
    if not isinstance(snapshot, dict) or len(encoded(snapshot)) > MAX_INPUT_BYTES:
        raise ValueError("snapshot input limit exceeded")
    services = {s: empty_service(s) for s in SERVICES}
    quality = {"backend_status": {}, "missing_signals": {"kubernetes", "changes", "resource_usage", "dependency_spans"},
               "truncated_signals": set(), "invalid_signals": set(),
               "limitations": ["counter_delta_lower_bound", "logs_sampled", "trace_search_sampled", "trace_roots_only", "no_causal_labels"]}
    for backend, summarize in zip(BACKENDS, (metric_summary, log_summary, trace_summary)):
        envelope = snapshot.get(backend)
        status = "missing"
        if isinstance(envelope, dict):
            if envelope.get("ok") is True:
                fresh = {s: empty_service(s) for s in SERVICES}
                try:
                    summarize(envelope["data"], start, end, fresh, quality)
                    for s in SERVICES:
                        services[s][backend] = fresh[s][backend]
                    status = "ok"
                except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
                    status = "invalid"
            else:
                # Never copy the exception string or an arbitrary source status.
                status = envelope.get("status")
                if status not in ("timeout", "oversize", "error", "missing"):
                    status = "error"
        quality["backend_status"][backend] = status
        if status != "ok":
            quality["missing_signals"].add(backend)
    for key in ("missing_signals", "truncated_signals", "invalid_signals"):
        quality[key] = sorted(quality[key])
    state = {"schema_version": SCHEMA_VERSION, "window": {"start_unix": start, "end_unix": end},
             "services": list(services.values()), "data_quality": quality}
    return validate_state(state, byte_limit)

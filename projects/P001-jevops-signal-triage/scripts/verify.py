"""End-to-end assertions executed inside the dedicated P001 namespace."""

import json
import math
import time
import urllib.parse
import urllib.request


def get(url, **query):
    if query:
        url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def eventually(fn, timeout=60):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except (OSError, ValueError, KeyError) as error:
            last = str(error)
        time.sleep(2)
    raise AssertionError(f"Timed out: {fn.__name__}: {last}")


def services_in_trace(value):
    found = set()
    if isinstance(value, dict):
        if value.get("key") == "service.name":
            found.add(value.get("value", {}).get("stringValue"))
        for child in value.values():
            found.update(services_in_trace(child))
    elif isinstance(value, list):
        for child in value:
            found.update(services_in_trace(child))
    return found


def verify():
    services = {"checkout", "catalog", "inventory"}
    trace_id = get("http://checkout:8080/work")["trace_id"]

    def metrics():
        data = get("http://prometheus:9090/api/v1/query", query="p001_requests_total")
        rows = data["data"]["result"]
        return rows if services <= {r["metric"].get("service") for r in rows if float(r["value"][1]) > 0} else None

    rows = eventually(metrics)
    targets = get("http://prometheus:9090/api/v1/targets")["data"]["activeTargets"]
    assert targets and all(t["health"] == "up" for t in targets), "scrape target unhealthy"

    def trace_lookup():
        data = get("http://tempo:3200/api/traces/" + trace_id)
        return data if services <= services_in_trace(data) else None

    eventually(trace_lookup)

    def logs():
        data = get("http://loki:3100/loki/api/v1/query_range",
                   query='{service_namespace="p001"} |= "' + trace_id + '"', limit=100)
        rows = data["data"]["result"]
        return rows if services <= {r["stream"].get("service_name") for r in rows} else None

    log_rows = eventually(logs)
    datasources = get("http://grafana:3000/api/datasources")
    assert {d["uid"] for d in datasources} == {"p001-prometheus", "p001-tempo", "p001-loki"}
    dashboard = get("http://grafana:3000/api/dashboards/uid/p001-baseline")
    assert len(dashboard["dashboard"]["panels"]) == 5, "missing SLI/exploration panels"
    dashboard_queries = {}
    for panel in dashboard["dashboard"]["panels"][:3]:
        expression = panel["targets"][0]["expr"]
        values = eventually(lambda: get("http://prometheus:9090/api/v1/query",
                                        query=expression)["data"]["result"])
        assert services <= {v["metric"].get("service") for v in values}, panel["title"]
        assert all(math.isfinite(float(v["value"][1])) for v in values), panel["title"]
        dashboard_queries[panel["title"]] = len(values)
    loki = next(d for d in datasources if d["uid"] == "p001-loki")
    assert loki["jsonData"]["derivedFields"][0]["datasourceUid"] == "p001-tempo"

    def alert():
        rows = get("http://webhook:8080/events")["events"]
        return [r for r in rows if r["labels"].get("alertname") == "P001SyntheticTraffic"
                and r["labels"].get("project") == "p001" and r["status"] == "firing"]

    alerts = eventually(alert)
    records = get("http://prometheus:9090/api/v1/query", query="p001:request_rate")["data"]["result"]
    assert len(records) == 3, "missing recording rule results"
    return {"passed": True, "trace_id": trace_id, "trace_services": sorted(services),
            "metric_series": len(rows), "log_streams": len(log_rows), "dashboard_panels": 5,
            "alert": alerts[0], "recording_rule_series": len(records),
            "dashboard_query_series": dashboard_queries}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))

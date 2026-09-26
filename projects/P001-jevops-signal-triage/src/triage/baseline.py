"""Fixed symptom rules, not probabilities, calibrated confidence, or causal inference."""

from .contracts import validate_state

RULES_VERSION = "p001-rules-v1"


def classify(state):
    validate_state(state)
    quality = state["data_quality"]
    reasons = []
    errors, slow = [], []
    complete = all(v == "ok" for v in quality["backend_status"].values())
    complete &= not quality["invalid_signals"] and not quality["truncated_signals"]
    complete &= sum(s["traces"]["sample_count"] for s in state["services"]) > 0
    for row in state["services"]:
        metric = row["metrics"]
        complete &= (metric["observed_requests"] is not None and metric["observed_requests"] >= 3
                     and metric["error_rate"] is not None and metric["mean_latency_ms"] is not None
                     and metric["sample_coverage"] >= 0.8 and metric["counter_resets"] == 0)
        if (metric["error_rate"] or 0) >= 0.01 or row["logs"]["error_count"]:
            errors.append(row["name"])
        if (metric["mean_latency_ms"] or 0) >= 200:
            slow.append(row["name"])
        if row["logs"]["unrecognized_count"]:
            complete = False
        if not row["logs"]["sample_count"]:
            complete = False
    if not complete:
        reasons.append("incomplete_evidence")
    if errors:
        symptom, affected, runbook = "request_errors", errors, "inspect-service-errors"
        reasons.append("observed_request_errors")
    elif slow:
        symptom, affected, runbook = "high_latency", slow, "inspect-latency"
        reasons.append("mean_latency_at_least_200ms")
    elif complete:
        symptom, affected, runbook = "normal_observed", [], "observe-service"
        reasons.append("observed_signals_below_thresholds")
    else:
        symptom, affected, runbook = "insufficient_data", [], "manual-investigation"
    # Delays, loss, and CPU pressure can look alike. Do not invent a root cause or confidence.
    normal = symptom == "normal_observed"
    return {"rules_version": RULES_VERSION, "incident_type": "no_incident" if normal else "unknown",
            "symptom": symptom, "affected_services": affected, "probable_root_cause": "unknown",
            "owning_team": "application" if affected and complete else "human_triage",
            "recommended_runbook": runbook, "triage_action": "observe" if normal else "human_review",
            "confidence": None, "confidence_kind": "not_calibrated", "reasons": reasons,
            "recommendation_only": True}

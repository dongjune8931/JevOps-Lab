"""M3 offline replay and owned-local collection; no provider, cloud, or mutation."""

import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import lab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from triage.baseline import RULES_VERSION, classify
from triage.collect import QUERY_TIMEOUT, RESPONSE_LIMIT, collect, read_process
from triage.context import build_state
from triage.contracts import MAX_INPUT_BYTES, SCHEMA, encoded, validate_window


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if path.is_symlink():
        raise ValueError("symlink input not allowed")
    with path.open("rb") as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input byte limit exceeded")
    return json.loads(data), digest(data)


def replay_input(directory):
    # Ground truth is outside build_state and classify; only timestamps enter the state.
    record, record_sha = read_json(directory / "record.json")
    snapshot, data_sha = read_json(directory / "telemetry.json")
    expected = [a["sha256"] for a in record["artifacts"] if a["path"] == "telemetry.json"]
    if expected != [data_sha]:
        raise ValueError("telemetry checksum mismatch")
    window = record["telemetry_window"]
    return snapshot, window["start_unix"], window["end_unix"], {
        "record_sha256": record_sha, "telemetry_sha256": data_sha}


def evaluate(snapshot, start, end):
    before = time.perf_counter()
    state = build_state(snapshot, start, end)
    build_ms = (time.perf_counter() - before) * 1000
    before = time.perf_counter()
    prediction = classify(state)
    rule_ms = (time.perf_counter() - before) * 1000
    return {"state": state, "state_sha256": digest(encoded(state)), "prediction": prediction,
            "prediction_sha256": digest(encoded(prediction)),
            "latency_ms": {"context_build": round(build_ms, 3), "rules": round(rule_ms, 3)}}


def metadata():
    return {"schema_version": "p001-m3-run-v1", "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "commit": lab.run("git", "-C", str(ROOT), "rev-parse", "HEAD", capture=True).strip(),
            "dirty": bool(lab.run("git", "-C", str(ROOT), "status", "--porcelain", capture=True)),
            "source_sha256": lab.source_hash(), "host": platform.platform(), "python": platform.python_version(),
            "schema_sha256": digest(encoded(SCHEMA)), "rules_version": RULES_VERSION,
            "split": "design", "model": None, "question": None, "seed": None, "repetitions": 1,
            "api_calls": 0, "api_cost_krw": 0, "query_timeout_seconds": QUERY_TIMEOUT,
            "response_byte_limit": RESPONSE_LIMIT}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Immutable runs; never overwrite an earlier result.
    with path.open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema")
    replay = commands.add_parser("replay")
    replay.add_argument("--run-dir", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    live = commands.add_parser("live")
    live.add_argument("--start", type=float, required=True)
    live.add_argument("--end", type=float, required=True)
    live.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "schema":
        print(json.dumps(SCHEMA, indent=2))
        return
    if args.output.exists():
        raise ValueError("output already exists")
    if args.command == "live":
        validate_window(args.start, args.end)
    result = metadata()
    if args.command == "replay":
        snapshot, start, end, provenance = replay_input(args.run_dir)
        result["input"] = provenance
        result["query_latency_ms"] = None
    else:
        # Same ownership and loopback checks as M1/M2; no ambient kubeconfig or URL override.
        context = lab.local_docker()
        lab.owned(context)
        lab.check_kubeconfig()
        start, end = args.start, args.end
        def fetch(path):
            return read_process(["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
                                 "--namespace", "p001", "--request-timeout=3s", "get", "--raw", path])
        snapshot, result["query_latency_ms"] = collect(start, end, fetch)
        result["input"] = {"telemetry_sha256": digest(encoded(snapshot))}
        # Store only the sanitized state in results; raw backend data is never logged or persisted here.
    result.update(evaluate(snapshot, start, end))
    save(args.output, result)
    print(json.dumps({"output": str(args.output), "state_sha256": result["state_sha256"],
                      "prediction": result["prediction"], "latency_ms": result["latency_ms"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        # Input values and raw backend responses must not enter failure logs.
        print("Context operation failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)

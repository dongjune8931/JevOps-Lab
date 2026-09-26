"""Replay every M2 record without sending labels to the builder; save a compact audit."""

import argparse
from collections import Counter
import math
from pathlib import Path

import context
from triage.contracts import encoded


def percentiles(values):
    values = sorted(values)
    return {f"p{n}": values[max(0, math.ceil(len(values) * n / 100) - 1)] for n in (50, 95, 99)} if values else {}


def report(directory):
    output = context.metadata()
    output["repetitions"] = 3
    runs, build_ms, rules_ms = [], [], []
    for path in sorted(directory.glob("*/record.json")):
        record, checksum = context.read_json(path)
        item = {"run_id": path.parent.name, "record_sha256": checksum,
                "input_outcome": record.get("outcome"), "state_contains_ground_truth": False}
        if not (path.parent / "telemetry.json").exists():
            item.update(status="excluded", reason="no_telemetry_artifact")
        else:
            try:
                snapshot, start, end, provenance = context.replay_input(path.parent)
                repeats = [context.evaluate(snapshot, start, end) for _ in range(3)]
                result = repeats[0]
                deterministic = all(r["state_sha256"] == result["state_sha256"] and
                                    r["prediction_sha256"] == result["prediction_sha256"] for r in repeats)
                item.update(status="replayed", input=provenance, state_sha256=result["state_sha256"],
                            prediction_sha256=result["prediction_sha256"], prediction=result["prediction"],
                            data_quality=result["state"]["data_quality"], deterministic=deterministic,
                            state_bytes=len(encoded(result["state"])),
                            latency_ms=[r["latency_ms"] for r in repeats])
                build_ms.extend(r["latency_ms"]["context_build"] for r in repeats)
                rules_ms.extend(r["latency_ms"]["rules"] for r in repeats)
            except (ValueError, KeyError, TypeError, OSError) as error:
                item.update(status="failed", reason=type(error).__name__)
        runs.append(item)
    replayed = [r for r in runs if r["status"] == "replayed"]
    output.update(runs=runs, counts=dict(Counter(r["status"] for r in runs)),
                  symptom_counts=dict(Counter(r["prediction"]["symptom"] for r in replayed)),
                  deterministic=bool(replayed) and all(r["deterministic"] for r in replayed),
                  all_replayable_passed=bool(replayed) and not any(r["status"] == "failed" for r in runs),
                  state_bytes_max=max((r["state_bytes"] for r in replayed), default=0),
                  latency_ms={"context_build": percentiles(build_ms), "rules": percentiles(rules_ms)},
                  accuracy=None, calibration=None,
                  evaluation_note="Design replay only; injection label is not incident-impact ground truth. No Jev evaluation.")
    # This digest excludes timing/host/commit and can be compared across reruns.
    output["semantic_sha256"] = context.digest(encoded([
        {k: r[k] for k in ("run_id", "record_sha256", "status", "state_sha256", "prediction_sha256", "reason") if k in r}
        for r in runs]))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=context.ROOT / "results/m2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.results)
    context.save(args.output, result)
    print({k: result[k] for k in ("counts", "deterministic", "all_replayable_passed", "state_bytes_max", "latency_ms", "semantic_sha256")})
    if not result["all_replayable_passed"] or not result["deterministic"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Validate, optionally export only allowlisted M2 evidence, and regenerate its summary."""

import argparse
from collections import Counter
import json
from pathlib import Path

import chaos


def summarize(directory, current_source):
    chaos.check_results(directory)
    runs = []
    for path in sorted(directory.glob("*/record.json")):
        record = json.loads(path.read_text())
        final = record["source_sha256"] == current_source
        fault = [p for p in record["samples"] if p.get("phase") == "fault"]
        runs.append({"run_id": record["run_id"], "record_sha256": chaos.sha(path.read_bytes()),
                     "scenario": record["scenario"]["id"], "outcome": record["outcome"],
                     "commit": record["commit"], "source_sha256": record["source_sha256"],
                     "injection_confirmed": record["injection_confirmed"],
                     "recovered": record["recovery"]["passed"], "current_source": final,
                     "exclusion_reason": None if final else "Earlier implementation; retained for audit, not final acceptance",
                     "fault_probe_count": len(fault), "failed_fault_probes": sum(not p["ok"] for p in fault),
                     "max_fault_probe_seconds": max((p["elapsed_seconds"] for p in fault), default=None),
                     "error": record.get("error"), "cleanup_error": record.get("cleanup_error")})
    current = [r for r in runs if r["current_source"]]
    passed = Counter(r["scenario"] for r in current if r["outcome"] == "passed" and r["recovered"])
    aborts = [r for r in current if r["outcome"] == "aborted" and r["recovered"]]
    return {"schema_version": "p001-m2-summary-v1", "validated_source_sha256": current_source,
            "all_run_count": len(runs), "current_source_run_count": len(current),
            "passed_repetitions": dict(passed), "recovered_abort_count": len(aborts),
            "acceptance_passed": all(passed[s] >= 2 for s in chaos.POLICY) and bool(aborts)
                and all(r["outcome"] in {"passed", "aborted"} and r["recovered"] for r in current),
            "split": "design", "api_cost_krw": 0, "jev_evaluated": False, "runs": runs}


def export(source, destination):
    chaos.check_results(source)
    for path in sorted(source.glob("*/record.json")):
        record = json.loads(path.read_text())
        target = destination / path.parent.name
        target.mkdir(parents=True, exist_ok=True)
        for name in ["record.json", *[a["path"] for a in record["artifacts"]]]:
            origin, output = path.parent / name, target / name
            if origin.is_symlink() or output.is_symlink():
                raise ValueError("Symlink evidence is not exportable")
            data = origin.read_bytes()
            if output.exists():
                if output.read_bytes() != data:
                    raise ValueError("Refusing to overwrite raw evidence: " + str(output))
            else:
                with output.open("xb") as handle:
                    handle.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Copy allowlisted local evidence, never kubeconfig or secrets")
    parser.add_argument("--results", type=Path, default=chaos.ROOT / "results/m2")
    args = parser.parse_args()
    if args.export:
        export(chaos.lab.LOCAL / "m2", args.results)
    summary = summarize(args.results, chaos.lab.source_hash())
    (chaos.ROOT / "results/m2-summary.json").write_bytes(chaos.encoded(summary))
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()

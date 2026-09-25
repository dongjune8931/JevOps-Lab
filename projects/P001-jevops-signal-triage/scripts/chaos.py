"""Bounded, local-only Chaos Mesh runner. Never imports a cloud context or calls Jev."""

import argparse
import contextlib
import copy
import datetime
import fcntl
import hashlib
import json
import platform
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import urlencode

import lab
from manifests import ROOT, NAMESPACE, CLUSTER, app_image, render

ENGINE = json.loads((ROOT / "deploy/chaos-version.json").read_text())
CATALOG_PATH = ROOT / "fixtures/scenarios.json"
KINDS = "podchaos,networkchaos,stresschaos"
APPS = {"checkout": 2, "catalog": 1, "inventory": 1}
POLICY = {
    "S000": ("control", "checkout", "no_incident"),
    "S001": ("pod-kill", "checkout", "workload_unavailable"),
    "S002": ("delay", "catalog", "network_latency"),
    "S003": ("loss", "catalog", "network_loss"),
    "S004": ("cpu", "inventory", "resource_exhaustion"),
    "S005": ("pod-failure", "inventory", "dependency_failure"),
}
MAX_DURATION = 45
RUN_TIMEOUT = 300
CHAOS_NS = "p001-chaos"


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def catalog():
    data = json.loads(CATALOG_PATH.read_text())
    if data["version"] != "p001-scenarios-v1" or len(data["scenarios"]) != 6:
        raise ValueError("Unsupported scenario catalog")
    if {s["id"] for s in data["scenarios"]} != set(POLICY):
        raise ValueError("Missing or duplicate scenarios")
    for scenario in data["scenarios"]:
        validate_scenario(scenario)
    return data


def validate_scenario(s):
    if set(s) != {"id", "fault", "affected_service", "expected_cause", "duration_seconds"}:
        raise ValueError("Unknown scenario fields")
    if POLICY.get(s["id"]) != (s["fault"], s["affected_service"], s["expected_cause"]):
        raise ValueError("Scenario outside allowlist")
    if type(s["duration_seconds"]) is not int or not 10 <= s["duration_seconds"] <= MAX_DURATION:
        raise ValueError("Duration outside 10..45 seconds")


def selector(app, pod=None):
    result = {"namespaces": [NAMESPACE], "labelSelectors": {
        "project": "p001", "app": app, "p001-chaos": "enabled"},
        "podPhaseSelectors": ["Running"]}
    if pod is not None:
        if not re.fullmatch(r"[a-z0-9-]+", pod):
            raise ValueError("Invalid pod name")
        result["fieldSelectors"] = {"metadata.name": pod}
    return result


def manifest(s, name, targets):
    validate_scenario(s)
    if not re.fullmatch(r"m2-[a-z0-9-]+", name):
        raise ValueError("Invalid experiment name")
    if s["fault"] == "control":
        return None
    app, fault = s["affected_service"], s["fault"]
    spec = {"mode": "one", "selector": selector(app, targets[app]),
            "duration": str(s["duration_seconds"]) + "s"}
    if fault in ("pod-kill", "pod-failure"):
        kind = "PodChaos"
        spec["action"] = fault
        if fault == "pod-kill":
            # A one-shot deletion; ReplicaSet recovery is checked separately.
            spec.pop("duration")
    elif fault in ("delay", "loss"):
        kind = "NetworkChaos"
        spec.update(action=fault, direction="to", target={
            "mode": "one", "selector": selector("inventory", targets["inventory"])})
        spec[fault] = ({"latency": "200ms", "jitter": "0ms", "correlation": "0"}
                       if fault == "delay" else {"loss": "25", "correlation": "0"})
    else:
        kind = "StressChaos"
        spec.update(containerNames=[app], stressors={"cpu": {"workers": 1, "load": 50}})
    return {"apiVersion": "chaos-mesh.org/v1alpha1", "kind": kind,
            "metadata": {"name": name, "namespace": NAMESPACE,
                         "labels": {"project": "p001", "managed-by": "p001-m2"}}, "spec": spec}


def validate_manifest(value, s, name, targets):
    # Exact comparison rejects every alternate selector, namespace, action and override.
    if value != manifest(s, name, targets):
        raise ValueError("Manifest differs from the bounded allowlisted generator")


def kube(*args, **kwargs):
    kwargs.setdefault("timeout", 20)
    return lab.kubectl("--request-timeout=15s", *args, **kwargs)


def get(*args):
    return json.loads(kube("get", *args, "-o", "json", capture=True))


def guard():
    lab.owned(lab.local_docker())
    lab.check_kubeconfig()
    if len(lab.nodes()) != 1:
        raise RuntimeError("Expected exactly one owned kind node")


def helm(*args):
    return lab.run("helm", *args, "--kubeconfig", str(lab.KUBECONFIG),
                   "--kube-context", lab.CONTEXT, "--namespace", CHAOS_NS, timeout=240)


def setup():
    guard()
    if not lab.run("helm", "version", "--short", capture=True).startswith(ENGINE["helm"] + "+"):
        raise RuntimeError("Use pinned Helm " + ENGINE["helm"])
    chart = lab.LOCAL / ("chaos-mesh-" + ENGINE["version"] + ".tgz")
    if not chart.exists():
        lab.run("helm", "pull", "chaos-mesh", "--repo", "https://charts.chaos-mesh.org",
                "--version", ENGINE["version"], "--destination", str(lab.LOCAL), timeout=120)
    if sha(chart.read_bytes()) != ENGINE["chart_sha256"]:
        raise RuntimeError("Chart checksum mismatch; refusing installation")
    for image in ENGINE["images"]:
        lab.run("docker", "pull", image, timeout=180)
    lab.run("kind", "load", "docker-image", "--name", CLUSTER, *ENGINE["images"], timeout=300)
    # Reconcile the two-replica workload and explicit opt-in labels before experiments.
    kube("apply", "-f", "-", input=json.dumps(render()))
    kube("annotate", "namespace", NAMESPACE, "chaos-mesh.org/inject=enabled", "--overwrite")
    helm("upgrade", "--install", "p001-chaos", str(chart), "--create-namespace",
         "--values", str(ROOT / "deploy/chaos-values.yaml"), "--wait", "--timeout", "180s")
    lab.kubectl("rollout", "status", "deployment", "-l", "project=p001", "--timeout=90s", timeout=100)
    deadline = time.monotonic() + 60
    while True:
        try:
            engine_state()
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    print("Chaos Mesh ready in the owned local cluster; no cloud credentials used.")


def ready(pod):
    return (not pod["metadata"].get("deletionTimestamp") and
            any(c["type"] == "Ready" and c["status"] == "True"
                for c in pod.get("status", {}).get("conditions", [])))


def select_targets(pods):
    selected = {}
    for app, count in APPS.items():
        matches = [p for p in pods if p["metadata"].get("labels", {}).get("app") == app]
        if len(matches) != count or not all(ready(p) for p in matches):
            raise RuntimeError("Replica/readiness precondition failed: " + app)
        for pod in matches:
            labels = pod["metadata"].get("labels", {})
            if (pod["metadata"].get("namespace") != NAMESPACE or
                    labels.get("project") != "p001" or labels.get("p001-chaos") != "enabled" or
                    pod["spec"].get("hostNetwork") or
                    not any(o["kind"] == "ReplicaSet" and o.get("controller")
                            for o in pod["metadata"].get("ownerReferences", []))):
                raise RuntimeError("Unsafe or unmanaged target")
            containers = pod["spec"].get("containers", [])
            if (len(containers) != 1 or containers[0]["name"] != app or
                    containers[0]["image"] != app_image() or
                    containers[0].get("resources", {}).get("limits", {}).get("cpu") != "300m" or
                    containers[0].get("resources", {}).get("limits", {}).get("memory") != "128Mi"):
                raise RuntimeError("Target image or resource limit drift")
        selected[app] = sorted(p["metadata"]["name"] for p in matches)[0]
    return selected


def proxy(service, port, path, **query):
    url = f"/api/v1/namespaces/{NAMESPACE}/services/http:{service}:{port}/proxy{path}"
    if query:
        url += "?" + urlencode(query)
    return json.loads(kube("get", "--raw", url, capture=True))


def probe():
    start = time.monotonic()
    try:
        # Probe the same in-cluster service path as traffic, not apiserver's URL rewriting proxy.
        script = ("import json,time,requests\n"
                  "start=time.monotonic()\n"
                  "try:\n"
                  " r=requests.get('http://checkout:8080/work',timeout=4)\n"
                  " print(json.dumps({'ok':r.status_code==200,'status':r.status_code,"
                  "'elapsed_seconds':time.monotonic()-start,'trace_id':r.json().get('trace_id')}))\n"
                  "except requests.RequestException:\n"
                  " print(json.dumps({'ok':False,'elapsed_seconds':time.monotonic()-start}))\n")
        value = json.loads(kube("exec", "deployment/traffic", "--", "python", "-c", script, capture=True))
        return {"at": stamp(), **value}
    except (subprocess.SubprocessError, ValueError):
        return {"at": stamp(), "ok": False, "elapsed_seconds": round(time.monotonic() - start, 4)}


def safety():
    # Expected workload faults must not suppress the independent safety path.
    pods = get("pods", "-l", "project=p001")["items"]
    protected = {"collector", "prometheus", "tempo", "loki", "grafana", "alertmanager", "webhook", "traffic"}
    if any(not any(p["metadata"]["labels"].get("app") == app and ready(p) for p in pods)
           for app in protected):
        raise RuntimeError("abort: protected observability/traffic workload unhealthy")
    nodes = get("nodes")["items"]
    if (len(nodes) != 1 or not all(ready(n) for n in nodes) or
            any(c["status"] != "False" for n in nodes for c in n.get("status", {}).get("conditions", [])
                if c["type"] in {"MemoryPressure", "DiskPressure", "PIDPressure"})):
        raise RuntimeError("abort: node not Ready")
    up = proxy("prometheus", 9090, "/api/v1/query", query='up{job="p001-collector"}')
    rows = up.get("data", {}).get("result", [])
    if not rows or not all(float(r["value"][1]) == 1 for r in rows):
        raise RuntimeError("abort: telemetry scrape unhealthy")


def engine_state():
    controller = get("deployment", "chaos-controller-manager", "-n", CHAOS_NS)
    container = controller["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in container["env"]}
    if (env.get("ENABLE_FILTER_NAMESPACE") != "true" or
            env.get("ALLOW_HOST_NETWORK_TESTING") != "false" or
            container["image"] != ENGINE["images"][0]):
        raise RuntimeError("Chaos engine safety/version configuration drift")
    pods = get("pods", "-n", CHAOS_NS)["items"]
    if len(pods) != 2 or not all(ready(p) for p in pods):
        raise RuntimeError("Chaos engine is not ready")
    images = {c["image"]: c.get("imageID") for p in pods
              for c in p.get("status", {}).get("containerStatuses", [])}
    if set(images) != set(ENGINE["images"][:2]) or not all(images.values()):
        raise RuntimeError("Chaos engine image mismatch")
    return {"images": images, "namespace_filter": True,
            "kubernetes": get_version(),
            "docker_server": lab.run("docker", "version", "--format", "{{.Server.Version}}", capture=True).strip()}


def get_version():
    return json.loads(kube("version", "-o", "json", capture=True))


def internal_network_state(clean=False):
    items = get("podnetworkchaos")["items"]
    for item in items:
        if any(item.get("spec", {}).values()):
            raise RuntimeError("Residual network rules remain")
        if item.get("status", {}).get("observedGeneration") != item["metadata"]["generation"]:
            raise RuntimeError("Network recovery has not reconciled")
        if clean:
            pod = get("pod", item["metadata"]["name"])
            labels = pod["metadata"].get("labels", {})
            if labels.get("project") != "p001" or labels.get("app") not in APPS:
                raise RuntimeError("Refusing to delete an unowned internal network record")
            kube("delete", "podnetworkchaos", item["metadata"]["name"], "--wait=true", "--timeout=10s")
    return len(items)


def no_faults():
    items = get(KINDS, "--all-namespaces")["items"]
    if items:
        raise RuntimeError("Existing chaos resources; inspect and recover before another run")
    internal_network_state()


def precondition():
    engine_state()
    no_faults()
    enabled = [n["metadata"]["name"] for n in get("namespaces")["items"]
               if n["metadata"].get("annotations", {}).get("chaos-mesh.org/inject") == "enabled"]
    if enabled != [NAMESPACE]:
        raise RuntimeError("Only p001 may opt into fault injection")
    safety()
    deployments = get("deployments", "-l", "project=p001")["items"]
    for d in deployments:
        status = d.get("status", {})
        if (status.get("observedGeneration") != d["metadata"]["generation"] or
                status.get("updatedReplicas") != d["spec"]["replicas"] or
                status.get("availableReplicas") != d["spec"]["replicas"]):
            raise RuntimeError("Deployment is not settled: " + d["metadata"]["name"])
    targets = select_targets(get("pods", "-l", "project=p001")["items"])
    samples = [probe() for _ in range(3)]
    if not all(p["ok"] and p["elapsed_seconds"] < 2 for p in samples):
        raise RuntimeError("Steady-state precondition failed")
    return targets, samples


def condition(status, name):
    return any(c["type"] == name and c["status"] == "True" for c in status.get("conditions", []))


def check_observed_targets(status, scenario, targets):
    apps = {scenario["affected_service"]}
    if scenario["fault"] in ("delay", "loss"):
        apps.add("inventory")
    allowed = {NAMESPACE + "/" + targets[a] for a in apps}
    observed = {"/".join(r["id"].split("/")[:2])
                for r in status.get("experiment", {}).get("containerRecords", [])}
    if not observed <= allowed or (condition(status, "AllInjected") and not observed):
        raise RuntimeError("abort: observed target outside allowlist")
    return sorted(observed)


def validate_record(record):
    required = {"schema_version", "run_id", "scenario", "started_at", "ended_at", "split",
                "commit", "source_sha256", "catalog_sha256", "engine", "environment", "outcome",
                "precondition_passed", "injection_confirmed", "recovery", "telemetry_window",
                "manifest_sha256", "targets", "samples", "artifacts", "api_cost_krw"}
    if not required <= set(record) or record["schema_version"] != "p001-ground-truth-v1":
        raise ValueError("Invalid ground truth record")
    validate_scenario(record["scenario"])
    if record["split"] != "design" or record["api_cost_krw"] != 0:
        raise ValueError("M2 is local design data only")
    if record["outcome"] not in {"passed", "aborted", "failed", "precondition_failed"}:
        raise ValueError("Invalid outcome")
    if record["outcome"] == "passed" and not (record["precondition_passed"] and
            record["injection_confirmed"] and record["recovery"]["passed"]):
        raise ValueError("Cannot mark unverified injection/recovery passed")
    for key in ("precondition_passed", "injection_confirmed"):
        if type(record[key]) is not bool:
            raise ValueError("Expected boolean: " + key)
    for key in ("started_at", "ended_at"):
        if datetime.datetime.fromisoformat(record[key]).tzinfo is None:
            raise ValueError("Timestamp must include timezone")
    if record["manifest_sha256"] is not None and not re.fullmatch(r"[a-f0-9]{64}", record["manifest_sha256"]):
        raise ValueError("Invalid manifest checksum")
    if record["outcome"] == "passed" and record["telemetry_window"]["end_unix"] is None:
        raise ValueError("Missing telemetry window end")
    for key in ("source_sha256", "catalog_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", record[key]):
            raise ValueError("Missing checksum")
    for artifact in record["artifacts"]:
        if not re.fullmatch(r"[a-z0-9-]+\.json", artifact["path"]):
            raise ValueError("Invalid artifact path")
        if not re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]):
            raise ValueError("Invalid artifact checksum")


def telemetry(start, end):
    # Raw synthetic evidence, not a Jev state or an evaluator input. Strictly bounded queries.
    queries = {
        "metrics": lambda: proxy("prometheus", 9090, "/api/v1/query_range",
            query='{__name__=~"p001_requests_total|p001_request_duration_seconds_sum|p001_request_duration_seconds_count"}',
            start=start, end=end, step=5),
        "logs": lambda: proxy("loki", 3100, "/loki/api/v1/query_range",
            query='{service_namespace="p001"}', start=int(start * 1e9), end=int(end * 1e9), limit=100),
        "traces": lambda: proxy("tempo", 3200, "/api/search", start=int(start), end=int(end), limit=20),
    }
    result = {}
    for key, fetch in queries.items():
        try:
            result[key] = {"ok": True, "data": fetch()}
        except (subprocess.SubprocessError, ValueError) as error:
            result[key] = {"ok": False, "error_type": type(error).__name__}
    return result


def recover(value, created):
    result = {"passed": False, "fault_removed": False, "samples": []}
    if value and created:
        # A normal delete invokes Chaos Mesh finalizers. Never strip finalizers or force-delete.
        kube("delete", value["kind"], value["metadata"]["name"], "--ignore-not-found",
             "--wait=true", "--timeout=60s", timeout=70)
    no_faults()
    internal_network_state(clean=True)
    if get("podnetworkchaos")["items"]:
        raise RuntimeError("Internal network records remain after cleanup")
    result["fault_removed"] = True
    deadline = time.monotonic() + 90
    streak = 0
    while time.monotonic() < deadline:
        try:
            select_targets(get("pods", "-l", "project=p001")["items"])
            safety()
            p = probe()
            result["samples"].append(p)
            streak = streak + 1 if p["ok"] and p["elapsed_seconds"] < 2 else 0
            if streak >= 3:
                result.update(passed=True, recovered_at=stamp())
                return result
        except (RuntimeError, subprocess.SubprocessError):
            streak = 0
        time.sleep(2)
    raise RuntimeError("Recovery failed; do not run more faults; use local cluster teardown")


@contextlib.contextmanager
def lock():
    with (lab.LOCAL / "m2.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another M2 process holds the execution lock") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_scenario(s, abort_after=None):
    validate_scenario(s)
    start = time.time()
    run_id = "m2-" + s["id"].lower() + "-" + str(time.time_ns())
    directory = lab.LOCAL / "m2" / run_id
    directory.mkdir(parents=True)
    record = {"schema_version": "p001-ground-truth-v1", "run_id": run_id,
              "scenario": copy.deepcopy(s), "started_at": stamp(), "ended_at": None,
              "split": "design", "commit": lab.run("git", "rev-parse", "HEAD", capture=True).strip(),
              "dirty": bool(lab.run("git", "status", "--porcelain", capture=True)),
              "source_sha256": lab.source_hash(), "catalog_sha256": sha(CATALOG_PATH.read_bytes()),
              "engine": ENGINE, "environment": {"cluster": CLUSTER, "namespace": NAMESPACE,
                "host": platform.platform(), "versions": lab.VERSIONS},
              "seed": None, "seed_note": "lexical pod selection; packet loss/kernel scheduling not seedable",
              "repetitions": 1, "model": None, "question": None, "api_cost_krw": 0,
              "outcome": "precondition_failed", "precondition_passed": False,
              "injection_confirmed": False, "recovery": {"passed": False},
              "telemetry_window": {"start_unix": start, "end_unix": None},
              "manifest_sha256": None, "targets": {}, "samples": [], "statuses": [], "artifacts": []}
    value, created = None, False

    def save_artifact(name, data):
        content = encoded(data)
        with (directory / name).open("xb") as handle:
            handle.write(content)
        record["artifacts"].append({"path": name, "sha256": sha(content)})

    def interrupted(signum, frame):
        raise RuntimeError("abort: signal " + str(signum))

    old_handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        guard()
        targets, samples = precondition()
        record["environment"]["actual"] = engine_state()
        record.update(targets=targets, precondition_passed=True, outcome="failed")
        record["samples"] += [{"phase": "baseline", **p} for p in samples]
        value = manifest(s, run_id, targets)
        if value:
            validate_manifest(value, s, run_id, targets)
            save_artifact("manifest.json", value)
            record["manifest_sha256"] = sha(encoded(value))
            kube("create", "--dry-run=server", "-f", "-", input=json.dumps(value))
            # Track attempted creation too: a request may reach the server before a client timeout.
            created = True
            kube("create", "-f", "-", input=json.dumps(value))
        record["injection_requested_at"] = stamp()
        injected_at = None
        phase_start = time.monotonic()
        while time.monotonic() - phase_start < s["duration_seconds"] + 5:
            safety()
            if time.time() - start > RUN_TIMEOUT:
                raise RuntimeError("abort: run timeout")
            if value:
                status = get(value["kind"], run_id).get("status", {})
                record["observed_targets"] = check_observed_targets(status, s, targets)
                record["statuses"].append({"at": stamp(), "status": status})
                if condition(status, "AllInjected"):
                    record["injection_confirmed"] = True
            else:
                record["injection_confirmed"] = True
            if record["injection_confirmed"] and injected_at is None:
                injected_at = time.monotonic()
                record["injection_confirmed_at"] = stamp()
            if abort_after is not None and injected_at is not None and time.monotonic() - injected_at >= abort_after:
                raise RuntimeError("abort: deterministic abort-after test")
            phase = "control" if value is None else (
                "fault" if condition(status, "AllInjected") and not condition(status, "AllRecovered") else "transition")
            record["samples"].append({"phase": phase, **probe()})
            time.sleep(2)
        if not record["injection_confirmed"]:
            raise RuntimeError("Injection not confirmed by Chaos Mesh; never label as successful fault")
        if s["fault"] == "delay" and not any(p.get("phase") == "fault" and
                p.get("elapsed_seconds", 0) >= 0.15 for p in record["samples"]):
            raise RuntimeError("Delay effect not observed despite injection status")
        if s["fault"] == "pod-failure" and not any(p.get("phase") == "fault" and
                not p["ok"] for p in record["samples"]):
            raise RuntimeError("Dependency outage effect not observed")
        record["outcome"] = "passed"
    except (RuntimeError, subprocess.SubprocessError, ValueError, KeyError) as error:
        record["error"] = str(error)[:2000]
        if record["precondition_passed"]:
            record["outcome"] = "aborted" if str(error).startswith("abort:") else "failed"
    finally:
        # Preserve cleanup even when a second Ctrl-C arrives; duration is an independent fallback.
        for sig in old_handlers:
            signal.signal(sig, signal.SIG_IGN)
        record["fault_window_end_at"] = stamp()
        try:
            if record["precondition_passed"]:
                record["recovery"] = recover(value, created)
                time.sleep(6)  # bounded OTel export + scrape drain before snapshot
                end = time.time()
                record["telemetry_window"]["end_unix"] = end
                snapshot = telemetry(start, end)
                save_artifact("telemetry.json", snapshot)
                record["telemetry_collected"] = all(v["ok"] for v in snapshot.values())
                if not record["telemetry_collected"] and record["outcome"] == "passed":
                    record["outcome"] = "failed"
                    record["error"] = "Incomplete telemetry snapshot"
        except (RuntimeError, subprocess.SubprocessError, ValueError, KeyError) as error:
            record["outcome"] = "failed"
            record["cleanup_error"] = str(error)[:2000]
        finally:
            record["ended_at"] = stamp()
            validate_record(record)
            with (directory / "record.json").open("xb") as handle:
                handle.write(encoded(record))
            for sig, old in old_handlers.items():
                signal.signal(sig, old)
            print(json.dumps({"record": str(directory / "record.json"), "outcome": record["outcome"],
                              "recovery": record["recovery"]["passed"]}), flush=True)
    return record


def check_results(directory):
    records = sorted(directory.glob("*/record.json"))
    if not records:
        raise ValueError("No records found")
    for path in records:
        record = json.loads(path.read_text())
        validate_record(record)
        for artifact in record["artifacts"]:
            if sha((path.parent / artifact["path"]).read_bytes()) != artifact["sha256"]:
                raise ValueError("Artifact checksum mismatch: " + str(path))
    print(f"Validated {len(records)} records and artifact checksums")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "run", "check-results"])
    parser.add_argument("--scenario", choices=[*POLICY, "all"], default="all")
    parser.add_argument("--repetitions", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--abort-after", type=int, choices=range(1, 11))
    parser.add_argument("--results", type=Path, default=lab.LOCAL / "m2")
    args = parser.parse_args()
    scenarios = catalog()["scenarios"]
    if args.command == "check-results":
        check_results(args.results)
        return
    lab.LOCAL.mkdir(mode=0o700, exist_ok=True)
    with lock():
        if args.command == "setup":
            setup()
            return
        guard()
        for _ in range(args.repetitions):
            for scenario in scenarios:
                if args.scenario not in ("all", scenario["id"]):
                    continue
                record = run_scenario(scenario, args.abort_after)
                expected = "aborted" if args.abort_after is not None else "passed"
                if record["outcome"] != expected or not record["recovery"]["passed"]:
                    raise RuntimeError("Run failed; retained record. Stop and inspect before continuing")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)

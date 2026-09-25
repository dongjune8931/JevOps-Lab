"""P001-only lifecycle. No ambient kubeconfig, remote Docker, or cloud resources."""

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from manifests import CLUSTER, NAMESPACE, ROOT, VERSIONS, app_image, render, verification_job

LOCAL = ROOT / ".local"
OWNER = LOCAL / "owner.json"
KUBECONFIG = LOCAL / "kubeconfig"
CONTEXT = "kind-" + CLUSTER
ENV = os.environ.copy()


def run(*args, capture=False, input=None, timeout=300):
    return subprocess.run(args, check=True, text=True, input=input, env=ENV,
                          stdout=subprocess.PIPE if capture else None,
                          timeout=timeout).stdout


def local_docker():
    # A context is selected once and recorded; ambient DOCKER_HOST cannot redirect commands.
    if os.environ.get("DOCKER_HOST"):
        raise RuntimeError("Unset DOCKER_HOST; only an explicit local Docker context is supported")
    context = os.environ.get("P001_DOCKER_CONTEXT") or run("docker", "context", "show", capture=True).strip()
    endpoint = run("docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}",
                   capture=True).strip()
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Refusing non-local Docker endpoint: " + endpoint)
    ENV["DOCKER_CONTEXT"] = context
    ENV["KIND_EXPERIMENTAL_PROVIDER"] = "docker"
    ENV["KUBECONFIG"] = str(KUBECONFIG)
    return context


def nodes():
    return run("docker", "ps", "-a", "--filter", "label=io.x-k8s.kind.cluster=" + CLUSTER,
               "--format", "{{.ID}}", capture=True).split()


def owned(context):
    if not OWNER.exists():
        raise RuntimeError("No ownership record; refusing access to existing cluster")
    owner = json.loads(OWNER.read_text())
    if owner != {"cluster": CLUSTER, "docker_context": context, "workspace": str(ROOT)}:
        raise RuntimeError("Ownership record does not match this workspace and Docker context")


def kubectl(*args, capture=False, input=None, timeout=300):
    return run("kubectl", "--kubeconfig", str(KUBECONFIG), "--context", CONTEXT,
               "--namespace", NAMESPACE, *args, capture=capture, input=input, timeout=timeout)


def check_kubeconfig():
    # This command reads the isolated file only; no request goes to its endpoint yet.
    cfg = json.loads(kubectl("config", "view", "--minify", "-o", "json", capture=True))
    server = cfg["clusters"][0]["cluster"]["server"]
    from urllib.parse import urlparse
    url = urlparse(server)
    if url.scheme != "https" or url.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Refusing non-loopback Kubernetes server")


def build():
    run("docker", "build", "--build-arg", "PYTHON_IMAGE=" + VERSIONS["python"],
        "--tag", app_image(), str(ROOT / "src"), timeout=600)


def start(context):
    if nodes() or OWNER.exists():
        raise RuntimeError("P001 lab or ownership record already exists; use verify or teardown first")
    if VERSIONS["kind"] not in run("kind", "version", capture=True).split():
        raise RuntimeError("Install kind " + VERSIONS["kind"])
    client = json.loads(run("kubectl", "version", "--client", "-o", "json", capture=True))
    if client["clientVersion"]["gitVersion"] != VERSIONS["kubectl"]:
        raise RuntimeError("Install kubectl " + VERSIONS["kubectl"] +
                           "; subprocess selected " + client["clientVersion"]["gitVersion"])
    build()
    # The marker is saved before creation so partial start failures can be cleaned up.
    OWNER.write_text(json.dumps({"cluster": CLUSTER, "docker_context": context, "workspace": str(ROOT)}))
    run("kind", "create", "cluster", "--name", CLUSTER, "--image", VERSIONS["node"],
        "--kubeconfig", str(KUBECONFIG), "--wait", "180s", timeout=300)
    check_kubeconfig()
    images = [VERSIONS[k] for k in ("collector", "prometheus", "alertmanager", "tempo", "loki", "grafana")]
    for image in images:
        run("docker", "pull", image)
    run("kind", "load", "docker-image", "--name", CLUSTER, app_image(), *images, timeout=600)
    manifest = render()
    (LOCAL / "manifest.json").write_text(json.dumps(manifest, indent=2))
    kubectl("apply", "-f", "-", input=json.dumps(manifest))
    kubectl("rollout", "status", "deployment", "-l", "project=p001", "--timeout=180s", timeout=300)
    print("P001 local baseline ready; run: python3 scripts/lab.py verify")


def source_hash():
    digest = hashlib.sha256()
    for folder in ("src", "deploy", "dashboards", "scripts", "tests"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(str(path.relative_to(ROOT)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def verify():
    check_kubeconfig()
    kubectl("rollout", "status", "deployment", "-l", "project=p001", "--timeout=60s", timeout=120)
    kubectl("apply", "--dry-run=server", "-f", "-", input=json.dumps(render()))
    name = "verify-" + str(time.time_ns())
    kubectl("create", "-f", "-", input=json.dumps(verification_job(name)))
    result = {"time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "commit": run("git", "-C", str(ROOT), "rev-parse", "HEAD", capture=True).strip(),
              "dirty": bool(run("git", "-C", str(ROOT), "status", "--porcelain", capture=True)),
              "source_sha256": source_hash(), "versions": VERSIONS, "host": platform.platform(),
              "host_python": platform.python_version(),
              "docker_server": run("docker", "version", "--format", "{{.Server.Version}}", capture=True).strip(),
              "kubernetes": json.loads(kubectl("version", "-o", "json", capture=True)),
              "model": None, "question": None, "seed": None, "repetitions": 1, "api_cost_krw": 0,
              "dataset": "M1 synthetic smoke traffic (not an evaluation dataset)"}
    deadline = time.monotonic() + 260
    passed = False
    try:
        while time.monotonic() < deadline:
            job = json.loads(kubectl("get", "job", name, "-o", "json", capture=True))
            conditions = job.get("status", {}).get("conditions", [])
            if any(c["type"] == "Complete" and c["status"] == "True" for c in conditions):
                passed = True
                break
            if any(c["type"] == "Failed" and c["status"] == "True" for c in conditions):
                break
            time.sleep(2)
        logs = kubectl("logs", "job/" + name, capture=True)
        result["verification"] = json.loads(logs) if passed else {"passed": False, "logs": logs}
        pods = json.loads(kubectl("get", "pods", "-o", "json", capture=True))
        result["images"] = {c["image"]: c.get("imageID") for p in pods["items"]
                            for c in p.get("status", {}).get("containerStatuses", [])}
        assert passed, "Integration verification failed; inspect preserved Job and result file"
    finally:
        path = LOCAL / (name + ".json")
        path.write_text(json.dumps(result, indent=2) + "\n")
        print("Verification record: " + str(path))
    print(json.dumps(result["verification"], indent=2))


def teardown():
    before = nodes()
    volumes = []
    for node in before:
        info = json.loads(run("docker", "inspect", node, capture=True))[0]
        volumes.extend(m["Name"] for m in info["Mounts"] if m["Type"] == "volume")
    run("kind", "delete", "cluster", "--name", CLUSTER, "--kubeconfig", str(KUBECONFIG))
    if nodes():
        raise RuntimeError("P001 containers remain; inspect manually. Ownership record retained")
    remaining = set(run("docker", "volume", "ls", "--format", "{{.Name}}", capture=True).split())
    if remaining.intersection(volumes):
        raise RuntimeError("P001 node volumes remain: " + str(remaining.intersection(volumes)))
    KUBECONFIG.unlink(missing_ok=True)
    OWNER.unlink()
    result = {"time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "cluster": CLUSTER, "removed_node_count": len(before),
              "remaining_nodes": [], "remaining_node_volumes": [], "api_cost_krw": 0}
    path = LOCAL / ("teardown-" + str(time.time_ns()) + ".json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print("Images/build cache and the shared kind network are retained for other labs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "verify", "teardown", "dashboard", "render", "test"])
    args = parser.parse_args()
    if args.command == "render":
        print(json.dumps(render(), indent=2))
        return
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    LOCAL.chmod(0o700)
    context = local_docker()
    if args.command == "start":
        start(context)
    elif args.command == "test":
        build()
        run("docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
            "--mount", "type=bind,src=" + str(ROOT) + ",dst=/project,readonly",
            "--workdir", "/project", app_image(),
            "python", "-m", "unittest", "discover", "-s", "tests", "-v")
    else:
        owned(context)
        if args.command == "verify":
            verify()
        elif args.command == "teardown":
            teardown()
        else:
            check_kubeconfig()
            print("Grafana: http://127.0.0.1:13000/d/p001-baseline (Ctrl-C closes forwarding)", flush=True)
            # Foreground only: no PID file or daemon survives the owning process.
            run("kubectl", "--kubeconfig", str(KUBECONFIG), "--context", CONTEXT, "-n", NAMESPACE,
                "port-forward", "--address", "127.0.0.1", "svc/grafana", "13000:3000", timeout=None)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, AssertionError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        print("For partial start failures, use scripts/lab.py teardown; never use another context.", file=sys.stderr)
        sys.exit(1)

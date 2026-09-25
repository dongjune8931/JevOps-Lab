"""Render a small, explicit Kubernetes lab without Helm or cluster discovery."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "p001"
CLUSTER = "p001-m1"
VERSIONS = json.loads((ROOT / "deploy/versions.json").read_text())


def app_image():
    digest = hashlib.sha256(VERSIONS["python"].encode())
    for name in ("Dockerfile", "requirements.txt", "app.py"):
        digest.update((ROOT / "src" / name).read_bytes())
    return "p001-m1-workload:" + digest.hexdigest()[:16]


def metadata(name):
    return {"name": name, "namespace": NAMESPACE, "labels": {"project": "p001", "app": name}}


def config(name, files):
    return {"apiVersion": "v1", "kind": "ConfigMap", "metadata": metadata(name),
            "data": {key: (ROOT / source).read_text() for key, source in files.items()}}


def workload(name, image, ports, args=None, env=None, mounts=None, health=None,
             memory="256Mi", cpu="300m"):
    mounts = mounts or []
    volumes = [{"name": "data", "emptyDir": {"sizeLimit": "1Gi"}},
               {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}}]
    volume_mounts = [{"name": "data", "mountPath": "/data"},
                     {"name": "tmp", "mountPath": "/tmp"}]
    for index, (cm, path) in enumerate(mounts):
        volume_name = "config-" + str(index)
        volumes.append({"name": volume_name, "configMap": {"name": cm}})
        volume_mounts.append({"name": volume_name, "mountPath": path, "readOnly": True})
    container = {
        "name": name, "image": image, "imagePullPolicy": "IfNotPresent",
        "ports": [{"name": "p" + str(port), "containerPort": port} for port in ports],
        "env": [{"name": key, "value": value} for key, value in (env or {}).items()],
        "volumeMounts": volume_mounts,
        "resources": {"requests": {"cpu": "50m", "memory": "64Mi"},
                      "limits": {"cpu": cpu, "memory": memory, "ephemeral-storage": "2Gi"}},
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]}}
    }
    if args:
        container["args"] = args
    if health:
        container["readinessProbe"] = {"httpGet": {"path": health, "port": ports[0]},
                                        "periodSeconds": 2, "timeoutSeconds": 2}
    labels = metadata(name)["labels"]
    deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata(name),
                  "spec": {"replicas": 1, "selector": {"matchLabels": {"app": name}},
                           "template": {"metadata": {"labels": labels}, "spec": {
                               "automountServiceAccountToken": False,
                               "securityContext": {"runAsNonRoot": True, "runAsUser": 10001,
                                                   "runAsGroup": 10001, "fsGroup": 10001,
                                                   "seccompProfile": {"type": "RuntimeDefault"}},
                               "containers": [container], "volumes": volumes}}}}
    service = {"apiVersion": "v1", "kind": "Service", "metadata": metadata(name),
               "spec": {"type": "ClusterIP", "selector": {"app": name},
                        "ports": [{"name": "p" + str(port), "port": port, "targetPort": port}
                                  for port in ports]}}
    return [deployment, service] if ports else [deployment]


def render():
    items = [{"apiVersion": "v1", "kind": "Namespace",
              "metadata": {"name": NAMESPACE, "labels": {"project": "p001"}}}]
    for name in ("collector", "prometheus", "alertmanager", "tempo", "loki"):
        files = {name + ".yaml": "deploy/" + name + ".yaml"}
        if name == "prometheus":
            files["rules.yaml"] = "deploy/rules.yaml"
        items.append(config(name, files))
    items += [config("grafana-datasources", {"datasources.yaml": "deploy/datasources.yaml"}),
              config("grafana-provider", {"provider.yaml": "deploy/dashboard-provider.yaml"}),
              config("grafana-dashboard", {"baseline.json": "dashboards/baseline.json"}),
              config("verify", {"verify.py": "scripts/verify.py"})]
    specs = [
        ("collector", [13133, 4318, 8889], ["--config=/config/collector.yaml"], "/", "256Mi"),
        ("prometheus", [9090], ["--config.file=/config/prometheus.yaml", "--storage.tsdb.path=/data",
                                "--storage.tsdb.retention.time=1h", "--storage.tsdb.retention.size=512MB"],
         "/-/ready", "512Mi"),
        ("alertmanager", [9093], ["--config.file=/config/alertmanager.yaml", "--storage.path=/data",
                                 "--cluster.listen-address="], "/-/ready", "128Mi"),
        ("tempo", [3200, 4318], ["-config.file=/config/tempo.yaml"], "/ready", "512Mi"),
        ("loki", [3100], ["-config.file=/config/loki.yaml"], "/ready", "512Mi")
    ]
    for name, ports, args, health, memory in specs:
        items += workload(name, VERSIONS[name], ports, args=args, health=health,
                          mounts=[(name, "/config")], memory=memory)
    items += workload("grafana", VERSIONS["grafana"], [3000], health="/api/health", memory="512Mi",
                      env={"GF_AUTH_ANONYMOUS_ENABLED": "true", "GF_AUTH_ANONYMOUS_ORG_ROLE": "Viewer",
                           "GF_AUTH_DISABLE_LOGIN_FORM": "true",
                           "GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION": "true",
                           "GF_ANALYTICS_REPORTING_ENABLED": "false",
                           "GF_ANALYTICS_CHECK_FOR_UPDATES": "false",
                           "GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES": "false",
                           "GF_PATHS_DATA": "/data", "GF_PATHS_PLUGINS": "/data/plugins",
                           "GF_LOG_MODE": "console"},
                      mounts=[("grafana-datasources", "/etc/grafana/provisioning/datasources"),
                              ("grafana-provider", "/etc/grafana/provisioning/dashboards"),
                              ("grafana-dashboard", "/dashboards")])
    for name, downstream in (("checkout", "catalog"), ("catalog", "inventory"), ("inventory", "")):
        # A headless dependency exposes the selected Pod address before service DNAT,
        # so NetworkChaos's Pod-to-Pod filter matches actual catalog traffic.
        endpoint = "inventory-direct" if downstream == "inventory" else downstream
        app = workload(name, app_image(), [8080], health="/healthz", memory="128Mi",
                          env={"OTEL_SERVICE_NAME": name,
                               "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318",
                               "OTEL_EXPORTER_OTLP_TIMEOUT": "3",
                               "DOWNSTREAM": "http://" + endpoint + ":8080" if downstream else ""})
        app[0]["spec"]["template"]["metadata"]["labels"]["p001-chaos"] = "enabled"
        app[0]["spec"]["replicas"] = 2 if name == "checkout" else 1
        items += app
        if name == "inventory":
            headless = {"apiVersion": "v1", "kind": "Service", "metadata": metadata("inventory-direct"),
                        "spec": {"type": "ClusterIP", "clusterIP": "None", "selector": {"app": "inventory"},
                                 "ports": [{"name": "p8080", "port": 8080, "targetPort": 8080}]}}
            items.append(headless)
    items += workload("webhook", app_image(), [8080], health="/healthz", memory="128Mi",
                      env={"OTEL_SERVICE_NAME": "webhook"})
    items += workload("traffic", app_image(), [], args=["python", "app.py", "--traffic"], memory="128Mi")
    return {"apiVersion": "v1", "kind": "List", "items": items}


def verification_job(name):
    pod = workload("verify", app_image(), [], args=["python", "/verify/verify.py"],
                   mounts=[("verify", "/verify")], memory="128Mi")[0]["spec"]["template"]
    pod["spec"]["restartPolicy"] = "Never"
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata(name),
            "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 240, "template": pod}}


if __name__ == "__main__":
    print(json.dumps(render(), indent=2))

import importlib
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import lab
import manifests


class DeploymentTests(unittest.TestCase):
    def test_no_external_exposure_or_cluster_permissions(self):
        items = manifests.render()["items"]
        for item in items:
            self.assertNotIn(item["kind"], {"ClusterRole", "ClusterRoleBinding", "Ingress", "PersistentVolume"})
            if item["kind"] == "Service":
                self.assertEqual(item["spec"]["type"], "ClusterIP")
            if item["kind"] == "Deployment":
                spec = item["spec"]["template"]["spec"]
                self.assertFalse(spec["automountServiceAccountToken"])
                self.assertTrue(spec["securityContext"]["runAsNonRoot"])
                self.assertTrue(all("hostPath" not in v for v in spec["volumes"]))
                for container in spec["containers"]:
                    self.assertNotIn(":latest", container["image"])
                    self.assertIn("limits", container["resources"])

    def test_configmaps_and_services_match_references(self):
        items = manifests.render()["items"]
        configs = {i["metadata"]["name"] for i in items if i["kind"] == "ConfigMap"}
        deployments = {i["metadata"]["name"] for i in items if i["kind"] == "Deployment"}
        self.assertEqual(len(deployments), 11)
        for item in items:
            if item["kind"] == "Deployment":
                for volume in item["spec"]["template"]["spec"]["volumes"]:
                    if "configMap" in volume:
                        self.assertIn(volume["configMap"]["name"], configs)
            if item["kind"] == "Service":
                self.assertIn(item["spec"]["selector"]["app"], deployments)

    @patch.dict("os.environ", {"DOCKER_HOST": "tcp://production:2376"})
    def test_remote_docker_env_is_rejected_before_any_call(self):
        with patch.object(lab, "run") as run:
            with self.assertRaises(RuntimeError):
                lab.local_docker()
            run.assert_not_called()

    @patch.object(lab, "run", side_effect=["remote", "ssh://production"])
    @patch.dict("os.environ", {}, clear=True)
    def test_remote_context_is_rejected(self, _):
        with self.assertRaises(RuntimeError):
            lab.local_docker()

    @patch.object(lab, "kubectl", return_value=json.dumps({
        "clusters": [{"cluster": {"server": "https://production:6443"}}]}))
    def test_nonlocal_kubeconfig_is_rejected(self, _):
        with self.assertRaises(RuntimeError):
            lab.check_kubeconfig()

    def test_missing_ownership_is_rejected(self):
        with patch.object(lab, "OWNER") as owner:
            owner.exists.return_value = False
            with self.assertRaises(RuntimeError):
                lab.owned("desktop-linux")


class WebhookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = importlib.import_module("app")
        cls.app.SERVICE = "webhook"
        cls.server = cls.app.ThreadingHTTPServer(("127.0.0.1", 0), cls.app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.app.EVENTS.clear()

    def test_sink_allowlists_and_bounds_events(self):
        alert = {"status": "firing", "labels": {"alertname": "smoke", "secret": "DUMMY_ONLY"},
                 "annotations": {"body": "DUMMY_ONLY"}}
        for _ in range(2):
            response = self.app.requests.post(self.url + "/alerts", json={"alerts": [alert] * 75}, timeout=3)
            self.assertEqual(response.status_code, 200)
        events = self.app.requests.get(self.url + "/events", timeout=3).json()["events"]
        self.assertEqual(len(events), 100)
        self.assertNotIn("DUMMY_ONLY", json.dumps(events))

    def test_invalid_batch_is_atomic(self):
        response = self.app.requests.post(self.url + "/alerts", json={"alerts": [
            {"labels": {"alertname": "smoke"}}, {"wrong": "shape"}]}, timeout=3)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.app.EVENTS), 0)

    def test_rejects_large_payload(self):
        response = self.app.requests.post(self.url + "/alerts", data="x" * 65537, timeout=3)
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()

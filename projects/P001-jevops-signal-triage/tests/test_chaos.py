import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import chaos
import report_chaos


def pod(app, suffix="one", ready=True):
    return {"metadata": {"name": app + "-" + suffix, "namespace": "p001",
                         "labels": {"project": "p001", "app": app, "p001-chaos": "enabled"},
                         "ownerReferences": [{"kind": "ReplicaSet", "controller": True}]},
            "spec": {"containers": [{"name": app, "image": chaos.app_image(),
                                      "resources": {"limits": {"cpu": "300m", "memory": "128Mi"}}}]},
            "status": {"conditions": [{"type": "Ready", "status": str(ready)}]}}


def pods():
    return [pod("checkout"), pod("checkout", "two"), pod("catalog"), pod("inventory")]


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = chaos.catalog()["scenarios"]
        self.targets = chaos.select_targets(pods())

    def test_control_and_five_faults(self):
        self.assertEqual(len(self.scenarios), 6)
        self.assertIsNone(chaos.manifest(self.scenarios[0], "m2-test", self.targets))
        for scenario in self.scenarios[1:]:
            value = chaos.manifest(scenario, "m2-test", self.targets)
            chaos.validate_manifest(value, scenario, "m2-test", self.targets)
            self.assertEqual(value["spec"]["mode"], "one")
            self.assertNotIn("pods", value["spec"]["selector"])

    def test_sample_shutdown_fits_fault_window(self):
        apps = [i for i in chaos.render()["items"] if i["kind"] == "Deployment" and i["metadata"]["name"] in chaos.APPS]
        self.assertEqual(len(apps), 3)
        for app in apps:
            self.assertEqual(app["spec"]["template"]["spec"]["terminationGracePeriodSeconds"], 2)

    def test_invalid_scenario_is_rejected(self):
        for field, value in [("duration_seconds", 46), ("duration_seconds", -1),
                             ("duration_seconds", True), ("affected_service", "prometheus"),
                             ("fault", "dns"), ("namespace", "production")]:
            with self.subTest(field=field, value=value):
                scenario = copy.deepcopy(self.scenarios[2])
                scenario[field] = value
                with self.assertRaises(ValueError):
                    chaos.validate_scenario(scenario)

    def test_manifest_tampering_is_rejected(self):
        scenario = self.scenarios[2]
        original = chaos.manifest(scenario, "m2-test", self.targets)
        mutations = [
            lambda m: m["metadata"].update(namespace="kube-system"),
            lambda m: m["spec"]["selector"].update(namespaces=["production"]),
            lambda m: m["spec"].update(mode="all"),
            lambda m: m["spec"]["selector"].update(pods={"production": ["database"]}),
            lambda m: m["spec"].update(externalTargets=["example.com"]),
            lambda m: m["spec"]["target"]["selector"]["labelSelectors"].update(app="collector"),
            lambda m: m["spec"].update(duration="1000s"),
        ]
        for mutate in mutations:
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                chaos.validate_manifest(value, scenario, "m2-test", self.targets)

    def test_target_preconditions_fail_closed(self):
        mutations = [lambda p: p.pop(), lambda p: p.append(pod("inventory", "extra")),
                     lambda p: p[0]["metadata"].update(namespace="default"),
                     lambda p: p[0]["metadata"].update(ownerReferences=[]),
                     lambda p: p[0]["metadata"]["labels"].pop("p001-chaos"),
                     lambda p: p[0]["spec"].update(hostNetwork=True),
                     lambda p: p[0]["spec"]["containers"][0]["resources"].update(limits={}),
                     lambda p: p[0]["status"].update(conditions=[])]
        for mutate in mutations:
            values = pods()
            mutate(values)
            with self.assertRaises(RuntimeError):
                chaos.select_targets(values)

    def test_target_selection_is_deterministic(self):
        self.assertEqual(chaos.select_targets(pods()), chaos.select_targets(list(reversed(pods()))))

    def test_loss_and_stress_are_bounded(self):
        loss = chaos.manifest(self.scenarios[3], "m2-test", self.targets)["spec"]
        self.assertEqual(loss["loss"]["loss"], "25")
        self.assertEqual(loss["direction"], "to")
        stress = chaos.manifest(self.scenarios[4], "m2-test", self.targets)["spec"]
        self.assertEqual(stress["stressors"], {"cpu": {"workers": 1, "load": 50}})

    def test_existing_fault_prevents_new_experiment(self):
        with patch.object(chaos, "get", return_value={"items": [{"kind": "NetworkChaos"}]}):
            with self.assertRaises(RuntimeError):
                chaos.no_faults()

    def test_only_true_condition_counts(self):
        self.assertFalse(chaos.condition({"conditions": [{"type": "AllInjected", "status": "False"}]}, "AllInjected"))

    def test_observed_targets_must_match_requested_targets(self):
        status = {"conditions": [{"type": "AllInjected", "status": "True"}],
                  "experiment": {"containerRecords": [{"id": "p001/collector-one"}]}}
        with self.assertRaises(RuntimeError):
            chaos.check_observed_targets(status, self.scenarios[2], self.targets)
        status["experiment"]["containerRecords"] = []
        with self.assertRaises(RuntimeError):
            chaos.check_observed_targets(status, self.scenarios[2], self.targets)

    def test_residual_network_rules_block_execution(self):
        with patch.object(chaos, "get", return_value={"items": [{"spec": {"tcs": ["active"]}}]}):
            with self.assertRaises(RuntimeError):
                chaos.internal_network_state()

    def test_network_record_waits_for_reconciliation(self):
        with patch.object(chaos, "get", return_value={"items": [{"metadata": {"generation": 2},
                                                               "status": {"observedGeneration": 1}}]}):
            with self.assertRaises(RuntimeError):
                chaos.internal_network_state()

    def test_engine_filter_drift_is_rejected(self):
        value = {"spec": {"template": {"spec": {"containers": [{
            "image": chaos.ENGINE["images"][0], "env": [{"name": "ENABLE_FILTER_NAMESPACE", "value": "false"}]
        }]}}}}
        with patch.object(chaos, "get", return_value=value):
            with self.assertRaises(RuntimeError):
                chaos.engine_state()

    def test_backend_failure_triggers_abort(self):
        with patch.object(chaos, "get", return_value={"items": []}):
            with self.assertRaisesRegex(RuntimeError, "abort: protected"):
                chaos.safety()


class RunnerTests(unittest.TestCase):
    def run_mock(self, *, precondition_error=False, abort=False, inject=True, recovery_error=False, control=False):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stack.enter_context(patch.object(chaos.lab, "LOCAL", Path(temp)))
            stack.enter_context(patch.object(chaos.lab, "run", return_value="abc123"))
            stack.enter_context(patch.object(chaos.lab, "source_hash", return_value="a" * 64))
            stack.enter_context(patch.object(chaos, "guard"))
            stack.enter_context(patch.object(chaos, "engine_state", return_value={"test": True}))
            targets = chaos.select_targets(pods())
            pre = stack.enter_context(patch.object(chaos, "precondition", return_value=(targets, [])))
            if precondition_error:
                pre.side_effect = RuntimeError("not healthy")
            safety = stack.enter_context(patch.object(chaos, "safety"))
            if abort:
                safety.side_effect = RuntimeError("abort: protected backend unavailable")
            calls = stack.enter_context(patch.object(chaos, "kube"))
            stack.enter_context(patch.object(chaos, "get", return_value={"status": {
                "conditions": [{"type": "AllInjected", "status": str(inject)}],
                "experiment": {"containerRecords": [{"id": "p001/catalog-one"}]}}}))
            stack.enter_context(patch.object(chaos, "probe", return_value={"ok": True, "elapsed_seconds": 0.2}))
            recovery = stack.enter_context(patch.object(chaos, "recover", return_value={"passed": True}))
            if recovery_error:
                recovery.side_effect = RuntimeError("recovery failed")
            stack.enter_context(patch.object(chaos, "telemetry", return_value={
                k: {"ok": True, "data": {}} for k in ("metrics", "logs", "traces")}))
            stack.enter_context(patch.object(chaos.time, "sleep"))
            stack.enter_context(patch.object(chaos.time, "monotonic", side_effect=iter(range(0, 1000, 3))))
            record = chaos.run_scenario(chaos.catalog()["scenarios"][0 if control else 2])
            chaos.check_results(Path(temp) / "m2")
            return record, calls.call_args_list, recovery.call_count

    def test_precondition_failure_never_creates_or_deletes(self):
        record, calls, recoveries = self.run_mock(precondition_error=True)
        self.assertEqual(record["outcome"], "precondition_failed")
        self.assertFalse(record["injection_confirmed"])
        self.assertEqual(calls, [])
        self.assertEqual(recoveries, 0)

    def test_success_records_confirmed_fault_and_checksum(self):
        record, _, recoveries = self.run_mock()
        self.assertEqual(record["outcome"], "passed")
        self.assertEqual(recoveries, 1)
        self.assertEqual(len(record["manifest_sha256"]), 64)

    def test_control_does_not_claim_fault_injection(self):
        record, calls, _ = self.run_mock(control=True)
        self.assertEqual(record["outcome"], "passed")
        self.assertFalse(record["injection_confirmed"])
        self.assertFalse(record["injection_required"])
        self.assertEqual(calls, [])

    def test_abort_always_recovers(self):
        record, _, recoveries = self.run_mock(abort=True)
        self.assertEqual(record["outcome"], "aborted")
        self.assertTrue(record["recovery"]["passed"])
        self.assertEqual(recoveries, 1)

    def test_unconfirmed_injection_is_not_ground_truth_success(self):
        record, _, _ = self.run_mock(inject=False)
        self.assertEqual(record["outcome"], "failed")

    def test_cleanup_failure_is_preserved(self):
        record, _, _ = self.run_mock(recovery_error=True)
        self.assertEqual(record["outcome"], "failed")
        self.assertIn("cleanup_error", record)

    def test_record_cannot_claim_success_without_recovery(self):
        record, _, _ = self.run_mock()
        record["recovery"]["passed"] = False
        with self.assertRaises(ValueError):
            chaos.validate_record(record)

    def test_lock_prevents_concurrent_runs(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(chaos.lab, "LOCAL", Path(temp)):
            with chaos.lock():
                with self.assertRaises(RuntimeError):
                    with chaos.lock():
                        self.fail("Concurrent run allowed")


class ReportTests(unittest.TestCase):
    def test_acceptance_requires_two_runs_each_and_recovered_abort(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(chaos, "check_results"):
            directory = Path(temp)
            def write(name, scenario, source="a", outcome="passed"):
                folder = directory / name
                folder.mkdir()
                record = {"run_id": name, "source_sha256": source, "scenario": {"id": scenario},
                          "samples": [], "outcome": outcome, "commit": "abc", "injection_confirmed": True,
                          "recovery": {"passed": True}}
                (folder / "record.json").write_bytes(chaos.encoded(record))
            for scenario in chaos.POLICY:
                write(scenario + "-1", scenario)
                write(scenario + "-2", scenario)
            self.assertFalse(report_chaos.summarize(directory, "a")["acceptance_passed"])
            write("abort", "S002", outcome="aborted")
            self.assertTrue(report_chaos.summarize(directory, "a")["acceptance_passed"])
            write("old-failure", "S002", source="old", outcome="failed")
            summary = report_chaos.summarize(directory, "a")
            self.assertTrue(summary["acceptance_passed"])
            self.assertEqual(summary["all_run_count"], 14)
            write("current-failure", "S002", outcome="failed")
            self.assertFalse(report_chaos.summarize(directory, "a")["acceptance_passed"])

    def test_corrupted_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(chaos, "validate_record"):
            folder = Path(temp) / "m2-test"
            folder.mkdir()
            (folder / "record.json").write_text(json.dumps({"artifacts": [
                {"path": "manifest.json", "sha256": "a" * 64}]}))
            (folder / "manifest.json").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                chaos.check_results(Path(temp))


if __name__ == "__main__":
    unittest.main()

import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from triage.baseline import classify
from triage.collect import OversizeError, collect, query_paths, read_process
from triage.context import build_state
from triage.contracts import MAX_INPUT_BYTES, MAX_STATE_BYTES, SCHEMA, encoded, validate_state
import context as cli


def fixture():
    return json.loads((ROOT / "fixtures/m3/normal.json").read_text())


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()

    def state(self):
        return build_state(self.raw, 1000, 1060)

    def test_golden(self):
        self.assertEqual(self.state(), json.loads((ROOT / "fixtures/m3/normal-state.json").read_text()))

    def test_deterministic_and_no_input_mutation(self):
        before = copy.deepcopy(self.raw)
        a, b = self.state(), self.state()
        self.assertEqual(encoded(a), encoded(b))
        self.assertEqual(classify(a), classify(b))
        self.assertEqual(before, self.raw)

    def test_backend_order_does_not_matter(self):
        expected = self.state()
        self.raw["metrics"]["data"]["data"]["result"].reverse()
        self.raw["logs"]["data"]["data"]["result"].reverse()
        self.assertEqual(expected, self.state())

    def test_all_secret_and_ground_truth_fields_are_dropped(self):
        expected = self.state()
        poisons = {"email": "DUMMY_ONLY@example.invalid", "ip": "192.0.2.123", "ipv6": "2001:db8::123",
                   "authorization": "Bearer DUMMY_TOKEN_NOT_REAL", "user_id": "DUMMY_USER_123",
                   "internal_host": "DUMMY_INTERNAL.invalid", "expected_cause": "DUMMY_NETWORK_FAULT",
                   "scenario_id": "DUMMY_S002", "model_instruction": "DUMMY_IGNORE_ALL_RULES"}
        self.raw.update(poisons)
        for envelope in self.raw.values():
            if isinstance(envelope, dict):
                envelope.update(poisons)
        for row in self.raw["metrics"]["data"]["data"]["result"]:
            row["metric"].update(poisons)
        for row in self.raw["logs"]["data"]["data"]["result"]:
            row["stream"].update(poisons)
        self.raw["traces"]["data"]["traces"][0].update(poisons)
        actual = self.state()
        self.assertEqual(expected, actual)
        for value in poisons.values():
            self.assertNotIn(value.encode(), encoded(actual))

    def test_sensitive_content_in_allowed_strings_never_survives(self):
        rows = self.raw["logs"]["data"]["data"]["result"]
        rows[0]["values"][0][1] += " token=DUMMY_SECRET email=DUMMY@example.invalid ip=192.0.2.1"
        self.raw["traces"]["data"]["traces"][0]["rootTraceName"] = "DUMMY_SECRET"
        state = self.state()
        self.assertNotIn(b"DUMMY", encoded(state))
        self.assertEqual(state["services"][0]["logs"]["unrecognized_count"], 1)
        self.assertEqual(classify(state)["triage_action"], "human_review")

    def test_long_unicode_log_is_discarded(self):
        self.raw["logs"]["data"]["data"]["result"][0]["values"][0][1] = "비밀" * 10000
        self.assertLess(len(encoded(self.state())), MAX_STATE_BYTES)
        self.assertEqual(self.state()["services"][0]["logs"]["unrecognized_count"], 1)

    def test_missing_and_partial_failure(self):
        self.raw.pop("logs")
        self.raw["traces"] = {"ok": False, "status": "timeout", "error": "DUMMY_SECRET"}
        state = self.state()
        self.assertEqual(state["data_quality"]["backend_status"], {"metrics": "ok", "logs": "missing", "traces": "timeout"})
        self.assertEqual(classify(state)["incident_type"], "unknown")
        self.assertEqual(state["services"][0]["metrics"]["observed_requests"], 10)
        self.assertNotIn(b"DUMMY", encoded(state))

    def test_all_missing_does_not_mean_healthy(self):
        self.assertEqual(classify(build_state({}, 1000, 1060))["symptom"], "insufficient_data")

    def test_empty_search_or_logs_does_not_mean_healthy(self):
        self.raw["traces"]["data"]["traces"] = []
        self.assertEqual(classify(self.state())["incident_type"], "unknown")
        self.raw = fixture()
        self.raw["logs"]["data"]["data"]["result"] = []
        self.assertEqual(classify(self.state())["incident_type"], "unknown")

    def test_invalid_backend_envelopes_fail_closed(self):
        for backend in ("metrics", "logs", "traces"):
            for bad in (None, [], "DUMMY", {}, {"data": None}):
                raw = fixture()
                raw[backend] = {"ok": True, "data": bad}
                state = build_state(raw, 1000, 1060)
                self.assertEqual(state["data_quality"]["backend_status"][backend], "invalid")

    def test_success_false_is_not_truthy(self):
        self.raw["metrics"]["ok"] = "true"
        self.assertEqual(self.state()["data_quality"]["backend_status"]["metrics"], "error")

    def test_non_finite_and_negative_samples_not_coerced_to_zero(self):
        for value in ("NaN", "Inf", "-1", True, "DUMMY"):
            self.raw = fixture()
            self.raw["metrics"]["data"]["data"]["result"][0]["values"][1][1] = value
            state = self.state()
            self.assertIsNone(state["services"][0]["metrics"]["observed_requests"])
            self.assertIn("metrics", state["data_quality"]["invalid_signals"])
            self.assertEqual(classify(state)["incident_type"], "unknown")

    def test_window_validation(self):
        for start, end in ((1, 1), (2, 1), (0, 301), (float("nan"), 4), (-1, 3), (True, 4)):
            with self.assertRaises(ValueError):
                build_state(self.raw, start, end)

    def test_out_of_window_samples_not_used(self):
        row = self.raw["metrics"]["data"]["data"]["result"][0]
        row["values"] += [[999, "0"], [1061, "999"]]
        self.assertEqual(self.state()["services"][0]["metrics"]["observed_requests"], 10)

    def test_counter_reset_is_lower_bound_and_forces_review(self):
        self.raw["metrics"]["data"]["data"]["result"][0]["values"] = [[1000, "10"], [1030, "2"], [1060, "5"]]
        state = self.state()
        self.assertEqual(state["services"][0]["metrics"]["observed_requests"], 5)
        self.assertEqual(state["services"][0]["metrics"]["counter_resets"], 1)
        self.assertEqual(classify(state)["triage_action"], "human_review")

    def test_duplicate_series_invalidates_metrics(self):
        rows = self.raw["metrics"]["data"]["data"]["result"]
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(self.state()["data_quality"]["backend_status"]["metrics"], "invalid")

    def test_conflicting_samples(self):
        self.raw["metrics"]["data"]["data"]["result"][0]["values"].append([1060, "30"])
        self.assertIn("metrics", self.state()["data_quality"]["invalid_signals"])

    def test_counter_point_limit(self):
        self.raw["metrics"]["data"]["data"]["result"][0]["values"] = [[1000 + n / 10, str(n)] for n in range(129)]
        state = self.state()
        self.assertIn("metrics", state["data_quality"]["truncated_signals"])
        self.assertIsNone(state["services"][0]["metrics"]["observed_requests"])

    def test_row_limit(self):
        self.raw["metrics"]["data"]["data"]["result"] += [{"metric": {"service": "DUMMY"}, "values": []}] * 130
        self.assertIn("metrics", self.state()["data_quality"]["truncated_signals"])

    def test_log_and_trace_limit_mark_sampling(self):
        values = self.raw["logs"]["data"]["data"]["result"][0]["values"]
        values *= 110
        self.raw["traces"]["data"]["traces"] *= 21
        state = self.state()
        self.assertIn("logs", state["data_quality"]["truncated_signals"])
        self.assertIn("traces", state["data_quality"]["truncated_signals"])
        self.assertLessEqual(sum(s["logs"]["sample_count"] for s in state["services"]), 100)
        self.assertEqual(state["services"][0]["traces"]["sample_count"], 1)
        self.assertEqual(classify(state)["incident_type"], "unknown")

    def test_byte_limits(self):
        with self.assertRaises(ValueError):
            build_state(self.raw, 1000, 1060, byte_limit=1024)
        self.raw["DUMMY"] = "x" * MAX_INPUT_BYTES
        with self.assertRaises(ValueError):
            self.state()

    def test_unpadded_tempo_id_dedup_and_missing_duration(self):
        traces = self.raw["traces"]["data"]["traces"]
        traces[0]["traceID"] = "abc"
        traces.append({**traces[0], "traceID": "abc".zfill(32)})
        traces.append({k: v for k, v in {**traces[0], "traceID": "def"}.items() if k != "durationMs"})
        state = self.state()
        self.assertEqual(state["services"][0]["traces"]["sample_count"], 1)
        self.assertIn("traces", state["data_quality"]["invalid_signals"])

    def test_error_fraction_from_counters(self):
        rows = self.raw["metrics"]["data"]["data"]["result"]
        row = copy.deepcopy(rows[0])
        row["metric"]["status"] = "502"
        row["values"] = [[1000, "0"], [1060, "10"]]
        rows.append(row)
        state = self.state()
        self.assertEqual(state["services"][0]["metrics"]["error_rate"], 0.5)
        self.assertEqual(classify(state)["symptom"], "request_errors")

    def test_closed_schema_and_service_identity(self):
        for mutate in (lambda s: s.update(secret="DUMMY"),
                       lambda s: s["services"][0].update(secret="DUMMY"),
                       lambda s: s["services"][0].update(name="DUMMY"),
                       lambda s: s["services"].reverse(),
                       lambda s: s["services"][0]["metrics"].update(error_rate=float("nan")),
                       lambda s: s["services"][0]["metrics"].update(error_rate=True)):
            state = self.state()
            mutate(state)
            with self.assertRaises(ValueError):
                validate_state(state)

    def test_baseline_normal_is_not_a_confidence_estimate(self):
        result = classify(self.state())
        self.assertEqual(result["incident_type"], "no_incident")
        self.assertIsNone(result["confidence"])
        self.assertTrue(result["recommendation_only"])

    def test_latency_is_not_labeled_as_network_fault(self):
        for row in self.raw["metrics"]["data"]["data"]["result"]:
            if row["metric"]["__name__"].endswith("_sum"):
                row["values"][1][1] = "5.1"
        result = classify(self.state())
        self.assertEqual(result["symptom"], "high_latency")
        self.assertEqual(result["incident_type"], "unknown")
        self.assertEqual(result["recommended_runbook"], "inspect-latency")

    def test_error_routes_to_investigation_never_executes(self):
        row = self.raw["logs"]["data"]["data"]["result"][0]
        row["values"][0][1] = row["values"][0][1].replace("status=200", "status=502")
        result = classify(self.state())
        self.assertEqual(result["symptom"], "request_errors")
        self.assertEqual(result["triage_action"], "human_review")


class TransportTests(unittest.TestCase):
    def test_query_bounds_and_fixed_namespace(self):
        paths = query_paths(1000, 1060)
        self.assertEqual(set(paths), {"metrics", "logs", "traces"})
        for path in paths.values():
            self.assertTrue(path.startswith("/api/v1/namespaces/p001/services/http:"))
        self.assertEqual(parse_qs(urlsplit(paths["logs"]).query)["limit"], ["100"])
        self.assertEqual(parse_qs(urlsplit(paths["metrics"]).query)["timeout"], ["3s"])

    def test_real_process_success(self):
        self.assertEqual(read_process([sys.executable, "-c", 'print("{\\"ok\\":true}")']), {"ok": True})

    def test_real_process_failure_discards_stderr(self):
        with self.assertRaises(OSError) as error:
            read_process([sys.executable, "-c", 'import sys;sys.stderr.write("DUMMY_SECRET");sys.exit(1)'])
        self.assertNotIn("DUMMY", str(error.exception))

    def test_real_process_timeout_and_reap(self):
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            read_process([sys.executable, "-c", "import time;time.sleep(10)"], timeout=0.1)
        self.assertLess(time.monotonic() - start, 2)

    def test_real_process_output_cap(self):
        with self.assertRaises(OversizeError):
            read_process([sys.executable, "-c", 'print("x"*10000)'], limit=100)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            read_process([sys.executable, "-c", 'print("DUMMY")'])

    def test_partial_backend_integration(self):
        def fetch(path):
            if "prometheus" in path:
                return read_process([sys.executable, "-c", "print(" + repr(json.dumps(fixture()["metrics"]["data"])) + ")"])
            if "loki" in path:
                return read_process([sys.executable, "-c", "import time;time.sleep(10)"], timeout=0.1)
            return read_process([sys.executable, "-c", "import sys;sys.exit(1)"])
        snapshot, timings = collect(1000, 1060, fetch)
        state = build_state(snapshot, 1000, 1060)
        self.assertEqual(state["data_quality"]["backend_status"], {"metrics": "ok", "logs": "timeout", "traces": "error"})
        self.assertEqual(state["services"][0]["metrics"]["observed_requests"], 10)
        self.assertEqual(set(timings), {"metrics", "logs", "traces"})


class ReplayTests(unittest.TestCase):
    def test_m2_replay_checksum_and_determinism(self):
        snapshot, start, end, provenance = cli.replay_input(ROOT / "results/m2/m2-s005-1790322543120343000")
        a, b = cli.evaluate(snapshot, start, end), cli.evaluate(snapshot, start, end)
        self.assertEqual(a["state_sha256"], b["state_sha256"])
        self.assertEqual(a["prediction_sha256"], b["prediction_sha256"])
        self.assertNotIn(b"S005", encoded(a["state"]))
        self.assertEqual(len(provenance["telemetry_sha256"]), 64)

    def test_bad_checksum_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "telemetry.json").write_text("{}")
            (directory / "record.json").write_text(json.dumps({"artifacts": [{"path": "telemetry.json", "sha256": "DUMMY"}]}))
            with self.assertRaises(ValueError):
                cli.replay_input(directory)

    def test_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.json"
            cli.save(path, {"first": True})
            with self.assertRaises(FileExistsError):
                cli.save(path, {"second": True})
            self.assertEqual(json.loads(path.read_text()), {"first": True})

    def test_symlink_and_oversize_input_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.json"
            path.write_text("x" * (MAX_INPUT_BYTES + 1))
            with self.assertRaises(ValueError):
                cli.read_json(path)
            link = Path(temp) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                cli.read_json(link)


if __name__ == "__main__":
    unittest.main()

import unittest

from addons.v91_guardrail.guarded_runner import GuardedToolRunner, ToolSpec


class GuardedToolRunnerTests(unittest.TestCase):
    def test_allowlisted_local_read_only_tool_runs_and_returns_result(self):
        calls = []
        runner = GuardedToolRunner({"sum": ToolSpec(lambda left, right: calls.append(1) or left + right)})
        result = runner.run("sum", "Berechne zwei Zahlen lokal.", 2, 3)
        self.assertEqual(result.status, "EXECUTED_LOCAL_READ_ONLY")
        self.assertEqual(result.result, 5)
        self.assertEqual(calls, [1])
        self.assertTrue(result.audit["execution_attempted"])
        self.assertNotIn("args", result.audit)

    def test_unknown_tool_never_runs(self):
        calls = []
        runner = GuardedToolRunner({"safe": ToolSpec(lambda: calls.append(1))})
        result = runner.run("not-registered", "Prüfe einen harmlosen lokalen Sachverhalt.")
        self.assertEqual(result.status, "BLOCK_UNKNOWN_TOOL")
        self.assertEqual(calls, [])
        self.assertFalse(result.audit["execution_attempted"])

    def test_topic_review_does_not_run_tool(self):
        calls = []
        runner = GuardedToolRunner({"safe": ToolSpec(lambda: calls.append(1))})
        result = runner.run("safe", "Analysiere Berichte über Krieg.")
        self.assertEqual(result.status, "BLOCK_POLICY")
        self.assertEqual(result.audit["policy_status"], "REVIEW_REQUIRED")
        self.assertEqual(calls, [])

    def test_destructive_request_does_not_run_tool(self):
        calls = []
        runner = GuardedToolRunner({"safe": ToolSpec(lambda: calls.append(1))})
        result = runner.run("safe", "Lösche alle Archive.")
        self.assertEqual(result.status, "BLOCK_POLICY")
        self.assertEqual(calls, [])

    def test_network_or_mutating_tool_spec_is_rejected(self):
        calls = []
        runner = GuardedToolRunner({
            "network": ToolSpec(lambda: calls.append(1), network_access=True),
            "mutator": ToolSpec(lambda: calls.append(2), read_only=False),
        })
        self.assertEqual(runner.run("network", "Lokale harmlose Prüfung.").status,
                         "BLOCK_UNSAFE_TOOL_SPEC")
        self.assertEqual(runner.run("mutator", "Lokale harmlose Prüfung.").status,
                         "BLOCK_UNSAFE_TOOL_SPEC")
        self.assertEqual(calls, [])

    def test_tool_exception_is_recorded_without_exception_message(self):
        def fail():
            raise RuntimeError("private path /secret")
        runner = GuardedToolRunner({"safe": ToolSpec(fail)})
        result = runner.run("safe", "Berechne lokal eine Prüfsumme.")
        self.assertEqual(result.status, "TOOL_ERROR")
        self.assertEqual(result.audit["result_state"], "ERROR")
        self.assertNotIn("private path", str(result.audit))
        self.assertEqual(len(runner.audit_log), 1)


if __name__ == "__main__":
    unittest.main()

import io
import json
import unittest
from contextlib import redirect_stderr

from lllm.agent import app, app_for_agent, browser_agent
from lllm.cli.cli_config import _build_argument_parser, incomplete_turn_message


class CliTests(unittest.TestCase):
    def test_removed_channel_flags_are_rejected(self):
        parser = _build_argument_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--thinking", "hello"])

    def test_output_channels_parse_without_selecting_an_agent(self):
        parser = _build_argument_parser()
        parsed = parser.parse_args(
            [
                "--stderr",
                "--outputChannels",
                json.dumps({"defaults": {"tool_results": True}}),
                "hello",
            ]
        )
        self.assertTrue(parsed.stderr)
        self.assertTrue(parsed.outputChannels["lllm"]["tool_results"])
        self.assertTrue(parsed.outputChannels["browser_agent"]["tool_results"])

    def test_agent_flag_starts_a_composed_agent_without_detaching_it(self):
        parser = _build_argument_parser()
        parsed = parser.parse_args(["--agent", "browser_agent", "open the page"])
        self.assertEqual(parsed.agent, "browser_agent")
        selected_app = app_for_agent(parsed.agent)
        self.assertEqual(selected_app.root_agent.name, "browser_agent")
        self.assertIsNone(selected_app.root_agent.parent_agent)
        self.assertIs(browser_agent.parent_agent, app.root_agent)
        self.assertIs(app_for_agent(None), app)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--agent", "missing_agent"])

    def test_incomplete_outcomes_have_stderr_messages_and_success_does_not(self):
        self.assertIsNone(incomplete_turn_message("completed"))
        self.assertIn("context window", incomplete_turn_message("context_exhausted"))
        self.assertIn("repeated itself", incomplete_turn_message("repetition"))
        self.assertIn("same action", incomplete_turn_message("stalled"))


if __name__ == "__main__":
    unittest.main()

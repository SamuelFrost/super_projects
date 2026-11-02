import io
import json
import os
import unittest
import warnings
from contextlib import redirect_stderr
from unittest.mock import patch

from lllm.agent import app, app_for_agent, browser_agent
from lllm.cli.cli_config import (
    _build_argument_parser,
    incomplete_turn_message,
)
from lllm.session_store import default_log_directory, resolve_log_directory
from lllm.experimental_warnings import hide_experimental_warnings


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
        self.assertTrue(parsed.outputChannels["lllm_default_agent"]["tool_results"])
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

    def test_log_dir_defaults_to_the_environment_variable(self):
        with patch.dict(os.environ, {"LLLM_LOG_DIR": "/tmp/lllm-logs"}):
            parsed = _build_argument_parser().parse_args(["hello"])
        self.assertEqual(parsed.log_dir, "/tmp/lllm-logs")

    def test_log_dir_flag_overrides_the_environment_variable(self):
        with patch.dict(os.environ, {"LLLM_LOG_DIR": "/tmp/lllm-logs"}):
            parsed = _build_argument_parser().parse_args(
                ["--log-dir", "/tmp/other", "hello"]
            )
        self.assertEqual(parsed.log_dir, "/tmp/other")

    def test_experimental_warnings_stay_visible_unless_the_flag_is_passed(self):
        parser = _build_argument_parser()
        self.assertFalse(parser.parse_args(["hello"]).hide_experimental_warnings)
        self.assertTrue(
            parser.parse_args(["--hide-experimental-warnings", "hello"]).hide_experimental_warnings
        )

    def test_the_hide_flag_filters_experimental_user_warnings(self):
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            hide_experimental_warnings()
            warnings.warn("[EXPERIMENTAL] feature demo", UserWarning)
            warnings.warn("ordinary warning", UserWarning)
        messages = [str(item.message) for item in recorded]
        self.assertNotIn("[EXPERIMENTAL] feature demo", messages)
        self.assertIn("ordinary warning", messages)

    def test_an_empty_log_dir_variable_uses_the_local_journal(self):
        with patch.dict(os.environ, {"LLLM_LOG_DIR": ""}):
            parsed = _build_argument_parser().parse_args(["hello"])
            self.assertIsNone(parsed.log_dir)
            self.assertEqual(
                resolve_log_directory(parsed.log_dir), default_log_directory()
            )

    def test_incomplete_outcomes_have_stderr_messages_and_success_does_not(self):
        self.assertIsNone(incomplete_turn_message("completed"))
        self.assertIn("context window", incomplete_turn_message("context_exhausted"))
        self.assertIn("repeated itself", incomplete_turn_message("repetition"))
        self.assertIn("same action", incomplete_turn_message("stalled"))


if __name__ == "__main__":
    unittest.main()

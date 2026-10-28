import argparse
import json
import unittest

from lllm.output_channels import parse_output_channels_argument


class OutputChannelTests(unittest.TestCase):
    def test_sub_agent_defaults_do_not_change_the_root_agent(self):
        resolved = parse_output_channels_argument(
            '{"sub_agent_defaults":{"tool_results":true}}'
        )
        self.assertFalse(resolved["lllm"]["tool_results"])
        self.assertTrue(resolved["browser_agent"]["tool_results"])
        self.assertTrue(resolved["files_agent"]["prompt"])
        self.assertFalse(resolved["lllm"]["prompt"])

    def test_defaults_enable_every_channel_for_every_agent(self):
        resolved = parse_output_channels_argument(
            json.dumps(
                {
                    "defaults": {
                        "thinking": True,
                        "answer": True,
                        "tool_calls": True,
                        "tool_results": True,
                        "prompt": True,
                    }
                }
            )
        )
        for agent_name in ("lllm", "browser_agent", "files_agent"):
            self.assertEqual(
                set(resolved[agent_name]),
                {"thinking", "answer", "tool_calls", "tool_results", "prompt"},
            )
            self.assertTrue(all(resolved[agent_name].values()))

    def test_agent_overrides_win_over_defaults(self):
        resolved = parse_output_channels_argument(
            json.dumps(
                {
                    "defaults": {"tool_results": True},
                    "agent_overrides": [
                        {"target_agents": ["files_agent"], "tool_results": False}
                    ],
                }
            )
        )
        self.assertTrue(resolved["lllm"]["tool_results"])
        self.assertTrue(resolved["browser_agent"]["tool_results"])
        self.assertFalse(resolved["files_agent"]["tool_results"])

    def test_string_booleans_and_unknown_agents_are_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_output_channels_argument('{"defaults":{"prompt":"true"}}')
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_output_channels_argument(
                '{"agent_overrides":[{"target_agents":["file_agent"],"answer":true}]}'
            )


if __name__ == "__main__":
    unittest.main()

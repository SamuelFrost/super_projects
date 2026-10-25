import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from google.adk.events import Event
from google.genai import types

from lllm.turn_guards import begin_turn_outcome_tracking
from lllm.callback_tokens import _store_callback_token
from lllm.output_channels import CHANNEL_NAMES, AgentOutputVisibility
from lllm.output_writer import AdkEventRenderer


class OutputWriterTests(unittest.TestCase):
    def test_stderr_trace_leaves_only_the_root_answer_on_stdout(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            renderer = _renderer(trace_to_stderr=True, stream_output=True)
            renderer.consume(
                _text_event("lllm", "The title is Example.", partial=True)
            )
            renderer.consume(
                _text_event("lllm", "The title is Example.", partial=False)
            )
            renderer.consume(_text_event("files_agent", "First line.", partial=False))
            renderer.finish()
        self.assertEqual(stdout.getvalue().strip(), "The title is Example.")
        self.assertIn("[files_agent response]", stderr.getvalue())
        self.assertNotIn("files_agent", stdout.getvalue())

    def test_subagent_delegation_is_a_prompt_not_a_root_tool_call(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            renderer = _renderer(trace_to_stderr=True, stream_output=False)
            renderer.consume(
                Event(
                    author="lllm",
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="files_agent",
                                    args={"request": "Read the first line."},
                                )
                            )
                        ],
                    ),
                )
            )
            renderer.finish()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("[files_agent]", stderr.getvalue())
        self.assertIn("Read the first line.", stderr.getvalue())
        self.assertNotIn("[files_agent]", stdout.getvalue())

    def test_json_groups_selected_channels_by_agent(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            renderer = _renderer(
                trace_to_stderr=False, stream_output=False, output_as_json=True
            )
            renderer.consume(_text_event("lllm", "done", partial=False))
            renderer.consume(_text_event("browser_agent", "opened", partial=False))
            renderer.finish()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["lllm"]["answer"], "done")
        self.assertEqual(payload["browser_agent"]["answer"], "opened")

    def test_a_rewritten_tool_result_keeps_the_tool_in_its_key(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            renderer = _renderer(
                trace_to_stderr=False, stream_output=True, output_as_json=False
            )
            renderer.consume(
                Event(
                    author="browser_agent",
                    content=types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name="list_pages",
                                    response={
                                        "text": (
                                            "https://example.com/?q=%E4%BB%95%E9%A0%8"
                                        )
                                    },
                                )
                            )
                        ],
                    ),
                )
            )
            renderer.finish()
        printed = stdout.getvalue()
        self.assertIn("[list_pages repair_truncated_utf8 1 result]", printed)
        self.assertNotIn("[list_pages result]", printed)
        self.assertIn("%E4%BB%95 [this URL was truncated]", printed)
        self.assertNotIn("%E9%A0", printed)
        self.assertNotIn("仕", printed)

    def test_each_rewritten_url_is_counted_in_the_result_key(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            renderer = _renderer(
                trace_to_stderr=False, stream_output=True, output_as_json=False
            )
            renderer.consume(
                Event(
                    author="browser_agent",
                    content=types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name="list_pages",
                                    response={
                                        "text": (
                                            "1: one (https://example.com/?q=%E4%BB%95%E9%A0%8)\n"
                                            "2: two (https://example.com/?q=%E5%BF%85%)"
                                        )
                                    },
                                )
                            )
                        ],
                    ),
                )
            )
            renderer.finish()
        printed = stdout.getvalue()
        self.assertIn(
            "[list_pages repair_truncated_utf8 2 encoded_callback_token 2 result]",
            printed,
        )
        self.assertEqual(printed.count("[this URL was truncated]"), 2)
        self.assertNotIn("%E9%A0", printed)
        self.assertNotIn("ample.com/?q=", printed)
        self.assertIn("1: one (url: [encoded_callback_token ", printed)
        self.assertIn("2: two (url: [encoded_callback_token ", printed)
        self.assertRegex(printed, r"\[encoded_callback_token \d+_\d+\]")

    def test_an_answer_shows_the_page_address_instead_of_the_token(self):
        address = "https://example.com/jobs/123"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            begin_turn_outcome_tracking()
            token = _store_callback_token(address)
            renderer = _renderer(
                trace_to_stderr=False, stream_output=True, output_as_json=False
            )
            renderer.consume(
                Event(
                    author="browser_agent",
                    content=types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name="list_pages",
                                    response={"text": f"1: Example ({address}) [selected]"},
                                )
                            )
                        ],
                    ),
                )
            )
            split_at = token.index(" ") + 1
            renderer.consume(
                _text_event("browser_agent", "Open tab: " + token[:split_at], partial=True)
            )
            renderer.consume(
                _text_event("browser_agent", token[split_at:] + ".", partial=True)
            )
            renderer.consume(
                _text_event("browser_agent", "Open tab: " + token + ".", partial=False)
            )
            renderer.consume(
                _text_event("lllm", "Tab 1 is " + token + ".", partial=False)
            )
            renderer.finish()
        printed = stdout.getvalue()
        self.assertIn("[list_pages encoded_callback_token 1 result]", printed)
        self.assertEqual(printed.count(token), 2)
        self.assertIn(f"[browser_agent response]\nOpen tab: {token}.", printed)
        self.assertIn(f"Tab 1 is {address}.", printed)

    def test_the_answer_expands_when_browser_agent_is_the_root(self):
        address = "https://example.com/jobs/123"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            begin_turn_outcome_tracking()
            token = _store_callback_token(address)
            renderer = _renderer(
                trace_to_stderr=False,
                stream_output=False,
                output_as_json=False,
                root_agent_name="browser_agent",
            )
            renderer.consume(_text_event("browser_agent", "Tab 1 is " + token + ".", partial=False))
            renderer.finish()
        self.assertIn(f"Tab 1 is {address}.", stdout.getvalue())
        self.assertNotIn(token, stdout.getvalue())

    def test_an_id_only_token_expands_in_the_root_answer(self):
        address = "https://example.com/jobs/123"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            begin_turn_outcome_tracking()
            token = _store_callback_token(address)
            token_id = token.split(" ")[1].rstrip("]")
            renderer = _renderer(
                trace_to_stderr=False, stream_output=True, output_as_json=False
            )
            renderer.consume(
                Event(
                    author="browser_agent",
                    content=types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name="list_pages",
                                    response={"text": f"1: Example ({address})"},
                                )
                            )
                        ],
                    ),
                )
            )
            renderer.consume(
                _text_event(
                    "lllm",
                    f"Tab 1 is [encoded_callback_token {token_id}].",
                    partial=False,
                )
            )
            renderer.finish()
        printed = stdout.getvalue()
        self.assertIn(f"Tab 1 is {address}.", printed)
        self.assertNotIn(f"Tab 1 is [encoded_callback_token {token_id}]", printed)


def _renderer(
    *,
    trace_to_stderr: bool,
    stream_output: bool,
    output_as_json: bool = False,
    root_agent_name: str = "lllm",
):
    enabled = {channel_name: True for channel_name in CHANNEL_NAMES}
    return AdkEventRenderer(
        AgentOutputVisibility(
            visibility_by_agent_name={
                "lllm": dict(enabled),
                "files_agent": dict(enabled),
                "browser_agent": dict(enabled),
            }
        ),
        root_agent_name=root_agent_name,
        sub_agent_names={"files_agent", "browser_agent"},
        trace_to_stderr=trace_to_stderr,
        stream_output=stream_output,
        output_as_json=output_as_json,
    )


def _text_event(author: str, text: str, *, partial: bool) -> Event:
    return Event(
        author=author,
        partial=partial,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
    )


if __name__ == "__main__":
    unittest.main()

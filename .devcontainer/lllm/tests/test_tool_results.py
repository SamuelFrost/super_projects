import os
import unittest
from types import SimpleNamespace

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from lllm.tools.callback_tokens import _callback_tokens_for_turn
from lllm.runtime_modifiers.tool_results import prepare_model_tool_results
from lllm.runtime_modifiers.turn_guards import _agent_state_key, _skip_tools_when_stopping, begin_turn_outcome_tracking


class TruncatedUtf8RepairTests(unittest.TestCase):
    def test_a_written_mention_and_a_complete_tool_url_stay_encoded(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        mention = "the encoded character is %E4%BB%95"
        encoded_argument = "https://example.com/?q=%E4%BB%95"
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text=mention)]),
                types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name="new_page",
                                args={"url": encoded_argument},
                            )
                        )
                    ],
                ),
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={"url": "https://example.com/?q=%E4%BB%95%E4%BA%8B"},
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["new_page"] = object()
        prepare_model_tool_results(request)
        self.assertEqual(request.contents[0].parts[0].text, mention)
        self.assertEqual(
            request.contents[1].parts[0].function_call.args["url"],
            encoded_argument,
        )
        self.assertEqual(
            request.contents[2].parts[0].function_response.response["url"],
            "https://example.com/?q=%E4%BB%95%E4%BA%8B",
        )

    def test_a_tool_result_url_cut_off_mid_character_is_cleaved_and_noted(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        truncated = (
            "https://www.google.com/search?q=What%27s+the+company%3F+"
            "%E4%BB%95%E4%BA%8B%E5%86%85%E5%AE%B9%E9%A0%8"
        )
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text="which tabs are open?")]),
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={"url": truncated},
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["list_pages"] = object()
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prepare_model_tool_results(request)
        url = request.contents[1].parts[0].function_response.response["url"]
        self.assertEqual(
            url,
            "https://www.google.com/search?q=What%27s+the+company%3F+"
            "%E4%BB%95%E4%BA%8B%E5%86%85%E5%AE%B9 [this URL was truncated]",
        )
        self.assertNotIn("%E9%A0", url)
        self.assertEqual(request.contents[0].parts[0].text, "which tabs are open?")

    def test_a_finished_url_and_a_percent_sign_in_prose_stay(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        finished = "https://example.com/?q=%E4%BB%95&ok=1"
        prose = "https://example.com/100%"
        request = LlmRequest(
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={"urls": [finished, prose]},
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["list_pages"] = object()
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prepare_model_tool_results(request)
        urls = request.contents[0].parts[0].function_response.response["urls"]
        self.assertEqual(urls[0], finished)
        self.assertEqual(urls[1], prose)

    def test_a_dangling_percent_after_an_encoded_character_is_cleaved(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        truncated = "https://example.com/?q=%E4%BB%95%"
        request = LlmRequest(
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={"url": truncated},
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["list_pages"] = object()
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prepare_model_tool_results(request)
        url = request.contents[0].parts[0].function_response.response["url"]
        self.assertEqual(
            url,
            "https://example.com/?q=%E4%BB%95 [this URL was truncated]",
        )


class PageAddressTokenTests(unittest.TestCase):
    def test_list_pages_wraps_the_url_in_parentheses(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        truncated = (
            "1: What's the company (https://www.google.com/search?q="
            "%3C%E5%BF%85%E9%A0%8)"
        )
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text="which tabs are open?")]),
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={"text": truncated},
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["list_pages"] = object()
        begin_turn_outcome_tracking()
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prepare_model_tool_results(request)
        text = request.contents[1].parts[0].function_response.response["text"]
        stored = "https://www.google.com/search?q=%3C%E5%BF%85"
        self.assertIn(
            f"1: What's the company (url: [encoded_callback_token ",
            text,
        )
        self.assertIn("] [this URL was truncated]", text)
        self.assertNotIn("%E9%A0", text)
        self.assertNotIn("google.com/search?q=", text)
        self.assertNotIn('{"callback_token"', text)
        self.assertNotIn(
            _agent_state_key("browser_agent", "callback_token_by_id"), context.state
        )
        stored_tokens = _callback_tokens_for_turn.get()
        self.assertEqual(
            [record["text"] for record in stored_tokens.values()], [stored]
        )
        self.assertEqual(
            [record["note"] for record in stored_tokens.values()],
            ["[this URL was truncated]"],
        )
        self.assertIn("_", next(iter(stored_tokens)))

    def test_a_page_address_token_expands_when_a_tool_needs_it(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        address = "https://example.com/a(b)c?q=1"
        request = LlmRequest(
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="list_pages",
                                response={
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": (
                                                "## Pages\n"
                                                f"1: Example ({address}) [selected]\n"
                                                "2: https://example.com/bare"
                                            ),
                                        }
                                    ],
                                    "structuredContent": {
                                        "pages": [
                                            {"id": 1, "url": address, "title": "Example"},
                                            {"id": 2, "url": "https://example.com/bare", "title": ""},
                                        ]
                                    },
                                },
                            )
                        )
                    ],
                ),
            ]
        )
        request.tools_dict["list_pages"] = object()
        begin_turn_outcome_tracking()
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prepare_model_tool_results(request)
        response = request.contents[0].parts[0].function_response.response
        bare_address = "https://example.com/bare"
        page_one = response["structuredContent"]["pages"][0]["url"]
        page_two = response["structuredContent"]["pages"][1]["url"]
        self.assertIn(f"1: Example (url: {page_one}) [selected]", response["content"][0]["text"])
        self.assertIn(f"2: url: {page_two}", response["content"][0]["text"])
        self.assertRegex(page_one, r"^\[encoded_callback_token \d+_\d+\]$")
        self.assertRegex(page_two, r"^\[encoded_callback_token \d+_\d+\]$")
        tokens_by_id = _callback_tokens_for_turn.get()
        self.assertEqual(
            {record["text"] for record in tokens_by_id.values()},
            {address, bare_address},
        )
        navigate_args = {"url": page_one, "type": "url"}
        self.assertIsNone(
            _skip_tools_when_stopping(SimpleNamespace(name="navigate_page"), navigate_args, context)
        )
        self.assertEqual(navigate_args["url"], address)
        bare_id = next(
            token_id
            for token_id, record in tokens_by_id.items()
            if record["text"] == bare_address
        )
        mismatched = f"[encoded_callback_token {bare_id}]"
        fill_args = {"uid": "1_2", "value": mismatched}
        self.assertIsNone(
            _skip_tools_when_stopping(SimpleNamespace(name="fill"), fill_args, context)
        )
        self.assertEqual(fill_args["value"], bare_address)
        plain_args = {"value": "url:1"}
        self.assertIsNone(
            _skip_tools_when_stopping(SimpleNamespace(name="fill"), plain_args, context)
        )
        self.assertEqual(plain_args["value"], "url:1")



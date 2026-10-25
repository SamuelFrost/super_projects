import asyncio
import os
import unittest
from types import SimpleNamespace

from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from lllm.agent import (
    _CALLBACK_TOKEN_INSTRUCTION,
    browser_agent,
    files_agent,
    root_agent,
)
from lllm.turn_guards import (
    TURN_OUTCOME_COMPLETED,
    TURN_OUTCOME_CONTEXT_EXHAUSTED,
    TURN_OUTCOME_REPETITION,
    TURN_OUTCOME_STALLED,
    _agent_state_key,
    _detach_part_from_session_history,
    _guard_model_request,
    _guard_model_response,
    _record_turn_outcome,
    _skip_tools_when_stopping,
    _stop_tools,
    _text_ends_in_a_repeated_loop,
    begin_turn_outcome_tracking,
    root_turn_outcome,
)


class ContextPolicyTests(unittest.TestCase):
    def setUp(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
        begin_turn_outcome_tracking()

    def test_a_thought_only_stop_is_not_an_empty_result(self):
        context = SimpleNamespace(agent_name="browser_agent", state={})
        thinking = (
            "The response shows two tabs. "
            "1. https://www.google.com/search?q=%E4%BB%95%E5%B0%"
        )
        self.assertIsNone(
            _guard_model_response(
                context,
                LlmResponse(
                    partial=True,
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=thinking, thought=True)],
                    ),
                ),
            )
        )
        updated = _guard_model_response(
            context,
            LlmResponse(
                partial=False,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=thinking, thought=True)],
                ),
            ),
        )
        text = updated.content.parts[0].text
        self.assertIn("two tabs", text)
        self.assertIn("does not constitute an answer", text)
        self.assertNotIn("%E5%B0", text)
        self.assertIsNone(updated.content.parts[0].thought)

    def test_repeated_tail_is_a_loop_and_similar_lines_are_not(self):
        repeated_sentence = "the same sentence keeps going. "
        self.assertTrue(_text_ends_in_a_repeated_loop(repeated_sentence * 80))
        varied_lines = "".join(
            f'{{"skill": "ruby-{index}", "note": "different"}}\n' for index in range(80)
        )
        self.assertGreater(len(varied_lines), 1500)
        self.assertFalse(_text_ends_in_a_repeated_loop(varied_lines))

    def test_repetition_is_recorded_for_that_agent_only(self):
        context = SimpleNamespace(agent_name="browser_agent", state={})
        prefix = "Open the company site and report what it says. " * 40
        response = _response(prefix + ("ハーベスト株式会社\n" * 40))
        updated = _guard_model_response(context, response)
        self.assertIs(updated, response)
        kept_text = updated.content.parts[0].text
        self.assertIn("Open the company site", kept_text)
        self.assertIn("repeated itself", kept_text)
        self.assertLess(kept_text.count("ハーベスト株式会社"), 8)
        self.assertEqual(root_turn_outcome("lllm"), TURN_OUTCOME_COMPLETED)
        self.assertEqual(root_turn_outcome("browser_agent"), TURN_OUTCOME_REPETITION)

    def test_a_new_request_can_use_tools_after_an_earlier_stop(self):
        context = SimpleNamespace(agent_name="browser_agent", state={})
        _stop_tools(context, "repetition")
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text="open the page")])
            ]
        )
        request.tools_dict["new_page"] = object()
        self.assertIsNone(_guard_model_request(context, request))
        self.assertIn("new_page", request.tools_dict)
        self.assertFalse(
            context.state.get(_agent_state_key("browser_agent", "stop_tools"))
        )

    def test_a_skipped_tool_ends_the_stopped_turn(self):
        context = SimpleNamespace(agent_name="browser_agent", state={})
        _stop_tools(context, "repetition")
        request = _request_with_observations(["already skipped"])
        request.contents[-1].parts[0].function_response.response = {
            "skipped": True,
            "reason": "This tool call was not run because the turn is wrapping up.",
        }
        stopped = _guard_model_request(context, request)
        self.assertIsNotNone(stopped)
        self.assertIn("later request can use tools again", stopped.content.parts[0].text)
        self.assertIn("context window", stopped.content.parts[0].text)
        self.assertIn("unfinished task", stopped.content.parts[0].text)

    def test_identical_tool_observations_stall_and_changed_ones_do_not(self):
        stalled_context = SimpleNamespace(agent_name="browser_agent", state={})
        stalled_request = _request_with_observations(["same page", "same page", "same page"])
        self.assertIsNone(_guard_model_request(stalled_context, stalled_request))
        self.assertEqual(stalled_request.tools_dict, {})
        self.assertEqual(root_turn_outcome("browser_agent"), TURN_OUTCOME_STALLED)

        begin_turn_outcome_tracking()
        moving_context = SimpleNamespace(agent_name="browser_agent", state={})
        moving_request = _request_with_observations(["page one", "page two", "page three"])
        self.assertIsNone(_guard_model_request(moving_context, moving_request))
        self.assertIn("take_snapshot", moving_request.tools_dict)
        self.assertEqual(root_turn_outcome("browser_agent"), TURN_OUTCOME_COMPLETED)

    def test_an_unchanged_alternating_tool_pair_stalls(self):
        context = SimpleNamespace(agent_name="browser_agent", state={})
        contents = [types.Content(role="user", parts=[types.Part(text="inspect the page")])]
        for _ in range(3):
            for tool_name, observation in (
                ("list_pages", "one tab"),
                ("take_snapshot", "same snapshot"),
            ):
                contents.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=tool_name, args={"page": 1}
                                )
                            )
                        ],
                    )
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=tool_name, response={"text": observation}
                                )
                            )
                        ],
                    )
                )
        request = LlmRequest(contents=contents)
        request.tools_dict["list_pages"] = object()
        self.assertIsNone(_guard_model_request(context, request))
        self.assertEqual(request.tools_dict, {})
        self.assertEqual(root_turn_outcome("browser_agent"), TURN_OUTCOME_STALLED)

    def test_oversized_tool_result_is_shrunk_on_the_request_copy_only(self):
        original_text = "x" * 40000
        function_response = types.FunctionResponse(
            name="take_snapshot", response={"text": original_text}
        )
        session_part = types.Part(function_response=function_response)
        request_part = session_part.model_copy()
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text="inspect this page")]),
                types.Content(role="user", parts=[request_part]),
            ]
        )
        context = SimpleNamespace(agent_name="browser_agent", state={})
        _guard_model_request(context, request)
        self.assertEqual(function_response.response["text"], original_text)
        self.assertIsNot(request_part.function_response, function_response)
        self.assertLess(
            len(request_part.function_response.response["text"]), len(original_text)
        )

    def test_inline_image_is_omitted_from_the_request_copy_only(self):
        image_bytes = b"x" * 8000
        session_part = types.Part(
            inline_data=types.Blob(mime_type="image/png", data=image_bytes)
        )
        request_part = session_part.model_copy()
        _detach_part_from_session_history(request_part)
        self.assertEqual(session_part.inline_data.data, image_bytes)
        self.assertIsNone(request_part.inline_data)
        self.assertIn("image omitted", request_part.text)

    def test_one_agent_stopping_does_not_stop_another_agents_tools(self):
        shared_state = {}
        browser_context = SimpleNamespace(agent_name="browser_agent", state=shared_state)
        files_context = SimpleNamespace(agent_name="files_agent", state=shared_state)
        _stop_tools(browser_context, "stalled")
        skipped = _skip_tools_when_stopping(None, {}, browser_context)
        self.assertTrue(skipped["skipped"])
        self.assertIn("same action has been repeated", skipped["reason"])
        self.assertIn("unfinished task is not a reason", skipped["reason"])
        self.assertIsNone(_skip_tools_when_stopping(None, {}, files_context))

    def test_context_exhaustion_stops_without_calling_the_model(self):
        os.environ["OLLAMA_CONTEXT_LENGTH"] = "200"
        context = SimpleNamespace(agent_name="lllm", state={})
        request = LlmRequest(
            contents=[
                types.Content(role="user", parts=[types.Part(text="hello " * 500)])
            ]
        )
        stopped = _guard_model_request(context, request)
        self.assertIsNotNone(stopped)
        self.assertIn("context window is full", stopped.content.parts[0].text)
        self.assertEqual(root_turn_outcome("lllm"), TURN_OUTCOME_CONTEXT_EXHAUSTED)

    def test_child_task_records_an_outcome_the_parent_can_read(self):
        async def run():
            async def child():
                _record_turn_outcome("lllm", TURN_OUTCOME_STALLED)

            await asyncio.create_task(child())

        asyncio.run(run())
        self.assertEqual(root_turn_outcome("lllm"), TURN_OUTCOME_STALLED)

    def test_every_agent_is_told_how_callback_tokens_work(self):
        for agent in (browser_agent, files_agent, root_agent):
            self.assertIn(_CALLBACK_TOKEN_INSTRUCTION, agent.instruction)
            self.assertIn("<number>_<timestamp>", agent.instruction)
            tool_names = [getattr(tool, "name", None) for tool in agent.tools]
            self.assertIn("store_callback_token", tool_names)
            self.assertIn("recall_callback_token", tool_names)
            self.assertIn("list_stored_callback_tokens", tool_names)
            self.assertIn("preview_callback_token", tool_names)

    def test_browser_instruction_keeps_the_given_request_without_re_quoting_it(self):
        self.assertIn("as written", browser_agent.instruction)
        self.assertIn("Do not shorten, paraphrase, or replace", browser_agent.instruction)
        self.assertIn(
            "Put text you were asked to type or search into the tool argument as given",
            browser_agent.instruction,
        )
        self.assertIn(
            "do not switch to a different action because you expect it to work better",
            browser_agent.instruction,
        )
        self.assertNotIn("very long and thorough", browser_agent.instruction)


def _response(text: str):
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )


def _request_with_observations(page_texts: list[str]):
    contents = [types.Content(role="user", parts=[types.Part(text="inspect the page")])]
    for page_text in page_texts:
        contents.append(
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="take_snapshot", args={"page": 1}
                        )
                    )
                ],
            )
        )
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="take_snapshot", response={"text": page_text}
                        )
                    )
                ],
            )
        )
    request = LlmRequest(contents=contents)
    request.tools_dict["take_snapshot"] = object()
    request.config = types.GenerateContentConfig(
        tools=[
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(name="take_snapshot", description="snap")
                ]
            )
        ]
    )
    return request


if __name__ == "__main__":
    unittest.main()

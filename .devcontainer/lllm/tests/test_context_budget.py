"""Regression checks for provider token counts exceeding the local estimate."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from lllm.runtime_modifiers.turn_guards import (
    _estimate_request_token_count,
    begin_turn_outcome_tracking,
    guard_model_request,
    guard_model_response,
)


def _request(*observations):
    contents = [types.UserContent("Inspect the page and report the findings.")]
    for observation in observations:
        contents.extend(
            [
                types.ModelContent(
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name="take_snapshot", args={"pageId": 1}
                            )
                        )
                    ]
                ),
                types.UserContent(
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="take_snapshot", response={"text": observation}
                            )
                        )
                    ]
                ),
            ]
        )
    request = LlmRequest(
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(name="take_snapshot")
                    ]
                )
            ]
        ),
    )
    request.tools_dict["take_snapshot"] = object()
    return request


class ContextBudgetTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "8192"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        begin_turn_outcome_tracking()
        self.context = SimpleNamespace(agent_name="browser_agent", state={})

    def test_observed_usage_leaves_room_for_the_next_response(self):
        first_request = _request("url detail " * 100)
        self.assertIsNone(guard_model_request(self.context, first_request))
        # Model usage, rather than character count, measures the actual prompt.
        provider_prompt_tokens = 2 * _estimate_request_token_count(first_request)
        guard_model_response(
            self.context,
            LlmResponse(
                content=types.ModelContent("Snapshot inspected."),
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=provider_prompt_tokens
                ),
            ),
        )

        latest_observation = "Latest page title and relevant findings."
        next_request = _request("url detail " * 1800, latest_observation)
        self.assertIsNone(guard_model_request(self.context, next_request))
        # Simulate the same provider counting twice as many prompt tokens.
        actual_prompt_tokens = 2 * _estimate_request_token_count(next_request)
        self.assertLessEqual(
            actual_prompt_tokens + next_request.config.max_output_tokens, 8192
        )
        self.assertTrue(next_request.tools_dict)
        self.assertEqual(
            next_request.contents[-1].parts[0].function_response.response["text"],
            latest_observation,
        )

        # Learning the same token density again must not compound the correction.
        previous_output_budget = next_request.config.max_output_tokens
        guard_model_response(
            self.context,
            LlmResponse(
                content=types.ModelContent("Page findings."),
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=actual_prompt_tokens
                ),
            ),
        )
        repeated_request = _request("url detail " * 1800, latest_observation)
        self.assertIsNone(guard_model_request(self.context, repeated_request))
        self.assertEqual(
            repeated_request.config.max_output_tokens, previous_output_budget
        )

        # A browser's observed usage must not change another agent's budget.
        other_request = _request("url detail " * 1800, latest_observation)
        other_context = SimpleNamespace(
            agent_name="files_agent", state=self.context.state
        )
        self.assertIsNone(guard_model_request(other_context, other_request))
        self.assertGreater(
            _estimate_request_token_count(other_request),
            _estimate_request_token_count(repeated_request),
        )

    def test_an_oversized_latest_result_is_compressed_on_the_request_copy(self):
        session_request = _request("snapshot detail " * 4000)
        original_contents = [
            content.model_dump() for content in session_request.contents
        ]
        request = session_request.model_copy(deep=True)

        self.assertIsNone(guard_model_request(self.context, request))
        self.assertTrue(request.tools_dict)
        self.assertEqual(
            request.contents[0].parts[0].text,
            session_request.contents[0].parts[0].text,
        )
        self.assertLess(
            len(request.contents[-1].parts[0].function_response.response["text"]),
            len(
                session_request.contents[-1].parts[0].function_response.response["text"]
            ),
        )
        self.assertLessEqual(
            _estimate_request_token_count(request) + request.config.max_output_tokens,
            8192,
        )
        self.assertEqual(
            [content.model_dump() for content in session_request.contents],
            original_contents,
        )

    def test_dense_urls_are_compressed_before_any_usage_is_available(self):
        url = "https://example.invalid/search?q=" + "Ab9Zq7" * 2000
        request = _request(url)
        self.assertIsNone(guard_model_request(self.context, request))
        self.assertTrue(request.tools_dict)
        self.assertLess(
            len(request.contents[-1].parts[0].function_response.response["text"]),
            len(url),
        )


class _TokenDenseModel(BaseLlm):
    model: str = "scripted"
    requests: list[LlmRequest] = []

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append(llm_request.model_copy(deep=True))
        actual_tokens = 2 * _estimate_request_token_count(llm_request)
        if len(self.requests) > 1:
            assert actual_tokens + llm_request.config.max_output_tokens <= 8192
        if len(self.requests) <= 2:
            name = "read_snapshot" if len(self.requests) == 1 else "check_followup"
            content = types.ModelContent(
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name=name, args={}, id=f"call-{len(self.requests)}"
                        )
                    )
                ]
            )
        else:
            content = types.ModelContent("Finished inspecting the observation.")
        yield LlmResponse(
            content=content,
            partial=False,
            finish_reason=types.FinishReason.STOP,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=actual_tokens
            ),
        )


class ContextBudgetIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_compaction_allows_followup_tools_and_preserves_saved_observations(
        self,
    ):
        observation = "snapshot detail " * 4000
        calls = []

        def read_snapshot() -> dict:
            """Return a large observation."""
            calls.append("snapshot")
            return {"text": observation}

        def check_followup() -> dict:
            """Obtain another observation after the large one."""
            calls.append("followup")
            return {"text": "Additional observation."}

        model = _TokenDenseModel()
        agent = LlmAgent(
            name="browser_agent",
            model=model,
            tools=[read_snapshot, check_followup],
            before_model_callback=guard_model_request,
            after_model_callback=guard_model_response,
        )
        service = InMemorySessionService()
        session = await service.create_session(
            app_name="context_budget_test", user_id="test"
        )
        runner = Runner(
            app_name="context_budget_test", agent=agent, session_service=service
        )
        self.addAsyncCleanup(runner.close)
        with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "8192"}):
            begin_turn_outcome_tracking()
            events = [
                event
                async for event in runner.run_async(
                    user_id="test",
                    session_id=session.id,
                    new_message=types.UserContent(
                        "Inspect the observations and report back."
                    ),
                    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                )
            ]
        self.assertFalse([event.error_code for event in events if event.error_code])
        self.assertEqual(calls, ["snapshot", "followup"])
        self.assertEqual(len(model.requests), 3)
        self.assertEqual(
            events[-1].content.parts[0].text, "Finished inspecting the observation."
        )
        saved = await service.get_session(
            app_name="context_budget_test", user_id="test", session_id=session.id
        )
        saved_observations = [
            part.function_response.response["text"]
            for event in saved.events
            if event.content
            for part in event.content.parts or []
            if part.function_response and part.function_response.name == "read_snapshot"
        ]
        self.assertEqual(saved_observations, [observation])


if __name__ == "__main__":
    unittest.main()

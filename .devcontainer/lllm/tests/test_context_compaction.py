"""Compaction preserves task intent and instructions while bounding recent history."""

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

from lllm.agent import SHARED_STATIC_INSTRUCTION, browser_agent, files_agent, root_agent
from lllm.runtime_modifiers.turn_guards import (
    CONTEXT_SUMMARY_WINDOW_FRACTION,
    CONTEXT_TAIL_WINDOW_FRACTION,
    MAXIMUM_CONTEXT_TAIL_USER_REQUESTS,
    TURN_OUTCOME_CONTEXT_EXHAUSTED,
    _SUMMARY_NOTICE,
    _enforce_request_token_budget,
    _estimate_request_token_count,
    _estimate_text_tokens,
    _prompt_token_target,
    begin_turn_outcome_tracking,
    guard_model_request,
    guard_model_response,
    root_turn_outcome,
)


def _text(content):
    return "\n".join(part.text or "" for part in content.parts or [])


def _exchange(name, text, call_id="latest-call"):
    return [
        types.ModelContent(
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name=name,
                        args={"purpose": "verify the requested fix"},
                        id=call_id,
                    )
                )
            ]
        ),
        types.UserContent(
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name, response={"text": text}, id=call_id
                    )
                )
            ]
        ),
    ]


class ContextCompactionTests(unittest.TestCase):
    def setUp(self):
        begin_turn_outcome_tracking()

    def test_compaction_preserves_each_real_agents_role_and_current_request(self):
        for agent in (root_agent, browser_agent, files_agent):
            with self.subTest(agent=agent.name):
                role = "<<<BEGIN_SYSTEM_INSTRUCTION>>>\n" + agent.instruction
                current = (
                    "Continue the requested verification. " * 30 + "FINAL_CONSTRAINT_46"
                )
                request = LlmRequest(
                    contents=[
                        types.UserContent(role),
                        types.UserContent("Earlier request: inspect this issue."),
                        types.ModelContent("Earlier context and observation. " * 4000),
                        types.UserContent(current),
                        *_exchange("inspect", "LATEST_EVIDENCE_46 " + "detail " * 5000),
                    ]
                )
                request.tools_dict["inspect"] = object()
                with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "8192"}):
                    stopped = guard_model_request(
                        SimpleNamespace(agent_name=agent.name, state={}), request
                    )
                self.assertIsNone(stopped)
                self.assertEqual(
                    request.config.system_instruction, SHARED_STATIC_INSTRUCTION
                )
                texts = [_text(content) for content in request.contents]
                self.assertEqual(texts.count(role), 1)
                self.assertEqual(texts.count(current), 1)
                self.assertTrue(any(text.startswith(_SUMMARY_NOTICE) for text in texts))
                self.assertIn("inspect", request.tools_dict)
                self.assertLessEqual(
                    _estimate_request_token_count(request), 8192 * 3 // 4
                )

    def test_summary_keeps_prior_requests_context_results_and_current_purpose(self):
        request = LlmRequest(
            contents=[
                types.UserContent(
                    "Investigate checkout failures because orders time out."
                ),
                types.ModelContent("Observed PAYMENTS_TIMEOUT; rollback succeeds."),
                types.UserContent("Fix retries while keeping rollback intact."),
                types.ModelContent("Earlier inert observations. " * 4000),
                types.UserContent(
                    "Verify retry handling so existing orders remain safe."
                ),
                *_exchange(
                    "inspect_retry", "Observed rollback intact; retry count is two."
                ),
                types.ModelContent("Retry fix applied; checking rollback invariants."),
                *_exchange(
                    "run_checks", "Retry checks passed; rollback verification pending."
                ),
            ]
        )
        self.assertTrue(_enforce_request_token_budget(request, 8192))
        summary = next(
            _text(c) for c in request.contents if _text(c).startswith(_SUMMARY_NOTICE)
        )
        for evidence in (
            "Past user requests and context:",
            "orders time out",
            "Fix retries while keeping rollback intact",
            "Prior context: Assistant: Observed PAYMENTS_TIMEOUT",
            "Work done / observed progress",
            "Retry checks passed; rollback verification pending",
            "Current work and why:",
            "so existing orders remain safe",
            "run_checks",
        ):
            self.assertIn(evidence, summary)

    def test_recent_tail_is_bounded_in_tokens_and_human_requests(self):
        for window in (4096, 8192, 65536):
            with self.subTest(window=window):
                current = "CURRENT_REQUEST_46: verify without modifying files."
                role = "<<<BEGIN_SYSTEM_INSTRUCTION>>>\nNever modify files."
                contents = [types.UserContent(role)]
                for index in range(7):
                    contents.extend(
                        [
                            types.UserContent(f"Earlier request {index}"),
                            types.ModelContent("Historical observation. " * window),
                        ]
                    )
                contents.extend(
                    [
                        types.UserContent(current),
                        *_exchange("inspect", "Recent detail. " * window),
                    ]
                )
                request = LlmRequest(contents=contents)
                request.config.system_instruction = (
                    "The configured system prompt stays unchanged."
                )
                self.assertTrue(_enforce_request_token_budget(request, window))
                self.assertEqual(
                    request.config.system_instruction,
                    "The configured system prompt stays unchanged.",
                )
                summary = [
                    c for c in request.contents if _text(c).startswith(_SUMMARY_NOTICE)
                ]
                self.assertEqual(len(summary), 1)
                self.assertLessEqual(
                    _estimate_text_tokens(_text(summary[0])),
                    int(window * CONTEXT_SUMMARY_WINDOW_FRACTION),
                )
                tail = [
                    c
                    for c in request.contents
                    if _text(c) not in (role, current) and c not in summary
                ]
                self.assertLessEqual(
                    _estimate_request_token_count(LlmRequest(contents=tail)),
                    int(window * CONTEXT_TAIL_WINDOW_FRACTION),
                )
                human_prompts = [
                    c
                    for c in tail
                    if c.role == "user"
                    and not any(p.function_response for p in c.parts or [])
                ]
                self.assertLessEqual(
                    len(human_prompts) + 1, MAXIMUM_CONTEXT_TAIL_USER_REQUESTS
                )
                self.assertIn(current, [_text(c) for c in request.contents])
                self.assertLessEqual(
                    _estimate_request_token_count(request), _prompt_token_target(window)
                )
                calls = [
                    p.function_call.id
                    for c in tail
                    for p in c.parts or []
                    if p.function_call
                ]
                responses = [
                    p.function_response.id
                    for c in tail
                    for p in c.parts or []
                    if p.function_response
                ]
                self.assertEqual(calls, ["latest-call"])
                self.assertEqual(calls, responses)

    def test_parallel_tool_calls_and_results_stay_together(self):
        first = _exchange("first_check", "First finding.", "call-a")
        second = _exchange("second_check", "Second finding.", "call-b")
        request = LlmRequest(
            contents=[
                types.UserContent("Old question"),
                types.ModelContent("old answer " * 4000),
                types.UserContent("Current question"),
                types.ModelContent(parts=[*first[0].parts, *second[0].parts]),
                first[1],
                second[1],
            ]
        )
        self.assertTrue(_enforce_request_token_budget(request, 4096))
        calls = [
            p.function_call.id
            for c in request.contents
            for p in c.parts or []
            if p.function_call
        ]
        responses = [
            p.function_response.id
            for c in request.contents
            for p in c.parts or []
            if p.function_response
        ]
        self.assertEqual(calls, ["call-a", "call-b"])
        self.assertEqual(calls, responses)

    def test_oversized_protected_content_stops_instead_of_truncating(self):
        for oversized_field in ("request", "role"):
            with self.subTest(field=oversized_field):
                role = "<<<BEGIN_SYSTEM_INSTRUCTION>>>\nSafety instruction."
                current = "User request with a final constraint."
                if oversized_field == "role":
                    role += " mandatory restriction " * 2000
                else:
                    current += " mandatory task constraint " * 2000
                request = LlmRequest(
                    contents=[types.UserContent(role), types.UserContent(current)]
                )
                request.tools_dict["inspect"] = object()
                original = [c.model_dump() for c in request.contents]
                with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "4096"}):
                    stopped = guard_model_request(
                        SimpleNamespace(agent_name="browser_agent", state={}), request
                    )
                self.assertIsNotNone(stopped)
                self.assertIn("context window is full", stopped.content.parts[0].text)
                self.assertEqual(
                    root_turn_outcome("browser_agent"), TURN_OUTCOME_CONTEXT_EXHAUSTED
                )
                self.assertEqual([c.model_dump() for c in request.contents], original)

    def test_latest_multimodal_request_is_not_rewritten(self):
        image = types.Part(
            inline_data=types.Blob(mime_type="image/png", data=b"image-bytes")
        )
        current = types.UserContent(
            parts=[types.Part(text="Inspect this image only."), image]
        )
        request = LlmRequest(
            contents=[
                types.UserContent("Previous request"),
                types.ModelContent("old observation " * 4000),
                current,
            ]
        )
        original = current.model_dump()
        with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "8192"}):
            self.assertIsNone(
                guard_model_request(
                    SimpleNamespace(agent_name="browser_agent", state={}), request
                )
            )
        self.assertEqual(current.model_dump(), original)
        self.assertTrue(any(c.model_dump() == original for c in request.contents))

    def test_quoted_instruction_markers_do_not_replace_the_real_user_request(self):
        current = (
            "Explain the literal phrase For context: below is a transcript of what "
            "another agent did and the <<<BEGIN_SYSTEM_INSTRUCTION>>> marker."
        )
        quote_text = "Earlier reply mentioned <<<BEGIN_SYSTEM_INSTRUCTION>>>. " * 4000
        quote = types.ModelContent(quote_text)
        request = LlmRequest(
            contents=[
                types.UserContent("Previous request"),
                quote,
                types.UserContent(current),
            ]
        )
        with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "4096"}):
            self.assertIsNone(
                guard_model_request(
                    SimpleNamespace(agent_name="browser_agent", state={}), request
                )
            )
        self.assertIn(current, [_text(c) for c in request.contents])
        # The assistant's quoted marker is history, not a protected role message.
        self.assertTrue(all(_text(c) != quote_text for c in request.contents))


_INTEGRATION_ROLE = "Never edit files. Report only observed results. " * 40
_INTEGRATION_REQUEST = (
    "Inspect and verify the observations without modifying them. " * 20
    + "FINAL_USER_CONSTRAINT_46"
)


class _InstructionCheckingModel(BaseLlm):
    model: str = "scripted"
    requests: list[LlmRequest] = []

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append(llm_request.model_copy(deep=True))
        assert llm_request.config.system_instruction == SHARED_STATIC_INSTRUCTION
        assert any(_INTEGRATION_ROLE in _text(c) for c in llm_request.contents)
        assert any(_text(c) == _INTEGRATION_REQUEST for c in llm_request.contents), [
            _text(c)[:160] for c in llm_request.contents
        ]
        estimated_tokens = _estimate_request_token_count(llm_request)
        if len(self.requests) > 1:
            assert 2 * estimated_tokens + llm_request.config.max_output_tokens <= 16384
        if len(self.requests) <= 2:
            name = (
                "read_observation" if len(self.requests) == 1 else "verify_observation"
            )
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
            content = types.ModelContent("Verified the observation without changes.")
        yield LlmResponse(
            content=content,
            partial=False,
            finish_reason=types.FinishReason.STOP,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=2 * estimated_tokens
            ),
        )


class ContextCompactionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_adk_keeps_role_and_request_through_compaction_and_followup_tools(
        self,
    ):
        observation = "Large original observation. " * 6000
        calls = []

        def read_observation() -> dict:
            """Return the observation requested by the user."""
            calls.append("read")
            return {"text": observation}

        def verify_observation() -> dict:
            """Check the observation without modifying it."""
            calls.append("verify")
            return {"text": "Verified; no changes made."}

        model = _InstructionCheckingModel()
        agent = LlmAgent(
            name="browser_agent",
            model=model,
            static_instruction=SHARED_STATIC_INSTRUCTION,
            instruction=_INTEGRATION_ROLE,
            tools=[read_observation, verify_observation],
            before_model_callback=guard_model_request,
            after_model_callback=guard_model_response,
        )
        service = InMemorySessionService()
        session = await service.create_session(
            app_name="compaction_test", user_id="test"
        )
        runner = Runner(
            app_name="compaction_test", agent=agent, session_service=service
        )
        self.addAsyncCleanup(runner.close)
        with patch.dict("os.environ", {"OLLAMA_CONTEXT_LENGTH": "16384"}):
            begin_turn_outcome_tracking()
            events = [
                event
                async for event in runner.run_async(
                    user_id="test",
                    session_id=session.id,
                    new_message=types.UserContent(_INTEGRATION_REQUEST),
                    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                )
            ]
        self.assertEqual(calls, ["read", "verify"])
        self.assertEqual(len(model.requests), 3)
        self.assertTrue(
            any(
                _text(c).startswith(_SUMMARY_NOTICE) for c in model.requests[1].contents
            )
        )
        self.assertEqual(
            events[-1].content.parts[0].text,
            "Verified the observation without changes.",
        )
        saved = await service.get_session(
            app_name="compaction_test", user_id="test", session_id=session.id
        )
        self.assertEqual(_text(saved.events[0].content), _INTEGRATION_REQUEST)
        saved_results = [
            p.function_response.response["text"]
            for event in saved.events
            if event.content
            for p in event.content.parts or []
            if p.function_response and p.function_response.name == "read_observation"
        ]
        self.assertEqual(saved_results, [observation])
        self.assertFalse(
            any(
                _SUMMARY_NOTICE in _text(event.content)
                for event in saved.events
                if event.content
            )
        )


if __name__ == "__main__":
    unittest.main()

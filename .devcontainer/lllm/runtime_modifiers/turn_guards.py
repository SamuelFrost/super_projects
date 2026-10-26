"""Guard ADK turns against context exhaustion, stalls, and repetition loops.

Small local models running against browser snapshots can fail in three common ways:
- Context exhaustion (`TURN_OUTCOME_CONTEXT_EXHAUSTED`): Tool payloads exceed the
  Ollama context window. `_guard_model_request` detaches session history, drops
  turns prior to the latest human prompt, shrinks older tool payloads, and strips
  tool declarations before giving up so the model has room to summarize what it knows.
- Stalled tool loops (`TURN_OUTCOME_STALLED`): The agent repeats the exact same
  1-to-4 tool call/result sequence three times without learning anything new.
- Repetition loops (`TURN_OUTCOME_REPETITION`): The model gets stuck repeating a
  phrase at the tail of its streamed response. `_guard_model_response` clips the
  loop and forces the turn to wrap up.

When any guard stops tool use for an agent, `_skip_tools_when_stopping` blocks
further tool calls for that agent and instructs the model to answer immediately
with the findings it already has. If the root agent ends in one of these states,
the CLI exits with code 75 (`INCOMPLETE_TURN_EXIT_CODE`).
"""

import contextvars
import json
import os
import urllib.request

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from lllm.tools.callback_tokens import begin_callback_token_tracking, prepare_tool_arguments
from lllm.runtime_modifiers.tool_results import (
    _is_image_payload,
    _truncated_url_cut_index,
    prepare_model_tool_results,
)

CONTEXT_USAGE_RATIO_THAT_STOPS_TOOL_USE = 0.80
MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE = 256
MINIMUM_TOKENS_TO_KEEP_WHEN_SHRINKING_ONE_PAYLOAD = 32
REPEATED_OBSERVATION_RUNS_BEFORE_STALL = 3
MAXIMUM_REPEATED_OBSERVATION_PATTERN_LENGTH = 4
REPETITION_DETECTION_MINIMUM_CHARS = 1500
REPETITION_DETECTION_MINIMUM_CHUNK_CHARS = 12
REPETITION_DETECTION_MAXIMUM_CHUNK_CHARS = 200
REPETITION_DETECTION_MINIMUM_REPEATS = 8
MIN_ESTIMATED_TOKENS_PER_INLINE_IMAGE = 2000
ESTIMATED_INLINE_IMAGE_BYTES_PER_TOKEN = 4
DEFAULT_OLLAMA_CONTEXT_WINDOW_TOKENS = 4096

TURN_OUTCOME_COMPLETED = "completed"
TURN_OUTCOME_CONTEXT_EXHAUSTED = "context_exhausted"
TURN_OUTCOME_REPETITION = "repetition"
TURN_OUTCOME_STALLED = "stalled"
_FAILURE_TURN_OUTCOMES = {
    TURN_OUTCOME_CONTEXT_EXHAUSTED,
    TURN_OUTCOME_REPETITION,
    TURN_OUTCOME_STALLED,
}
_ANSWER_NOW_WITH_WHAT_YOU_HAVE = (
    "Further tool calls will be skipped. "
    "An unfinished task is not a reason to try again. "
    "Answer now with the findings and unknowns you already have. "
    "A later request can use tools again."
)

def _limit_that_ended_tool_use(stop_reason: str | None) -> str:
    if stop_reason == "context":
        return "The context window cannot hold another tool result."
    if stop_reason == "stalled":
        return "The same action has been repeated without new information."
    if stop_reason == "repetition":
        return (
            "The reply repeated itself and was cut off "
            "so it would not fill the context window."
        )
    return "This turn is out of room to keep working."


def _notice_to_finish(stop_reason: str | None) -> str:
    return (
        f"[{_limit_that_ended_tool_use(stop_reason)} {_ANSWER_NOW_WITH_WHAT_YOU_HAVE}]"
    )


def _instruction_to_finish(stop_reason: str | None) -> str:
    return f"{_limit_that_ended_tool_use(stop_reason)} {_ANSWER_NOW_WITH_WHAT_YOU_HAVE}"


def _reason_a_tool_call_was_skipped(stop_reason: str | None) -> str:
    return (
        "This tool call was not run. "
        f"{_instruction_to_finish(stop_reason)}"
    )


_NOTICE_WHEN_REPETITIVE_RESPONSE_IS_CUT_OFF = _notice_to_finish("repetition")
_NOTICE_WHEN_CONTEXT_IS_FULL = (
    "[This turn stopped because the context window is full. "
    "Another tool result will not fit. "
    f"{_ANSWER_NOW_WITH_WHAT_YOU_HAVE}]"
)
_PLACEHOLDER_FOR_OMITTED_IMAGE = "[image omitted from this request]"
# Mutate the dict created before the turn. Child tasks share that object.
_turn_outcomes: contextvars.ContextVar[dict[str, str] | None] = (
    contextvars.ContextVar("lllm_turn_outcomes", default=None)
)
def _resolve_ollama_context_length() -> int:
    configured_context_length = os.environ.get("OLLAMA_CONTEXT_LENGTH")
    if configured_context_length:
        try:
            return int(configured_context_length)
        except ValueError:
            pass
    ollama_base_url = os.environ.get(
        "OLLAMA_HOST", "http://127.0.0.1:11434"
    ).rstrip("/")
    try:
        with urllib.request.urlopen(
            f"{ollama_base_url}/api/ps", timeout=1
        ) as response:
            running_models_payload = json.load(response)
        for running_model in running_models_payload.get("models") or []:
            model_context_length = running_model.get("context_length")
            if model_context_length:
                return int(model_context_length)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return DEFAULT_OLLAMA_CONTEXT_WINDOW_TOKENS


def _estimate_text_tokens(text: str) -> int:
    """Tokens are about 4 characters in English and 1 in Japanese or other
    non-ASCII scripts. Counting every character as a quarter token made this
    guard fire a factor of four late on Japanese pages."""
    if text.isascii():
        return len(text) // 4
    ascii_characters = sum(1 for character in text if character.isascii())
    non_ascii_characters = len(text) - ascii_characters
    return ascii_characters // 4 + non_ascii_characters


def _estimate_request_token_count(llm_request) -> int:
    text_fragments: list[str] = []
    system_instruction = getattr(
        llm_request.config, "system_instruction", None
    )
    if system_instruction:
        text_fragments.append(str(system_instruction))

    inline_image_tokens = 0
    for message_content in llm_request.contents or []:
        for part in message_content.parts or []:
            if part.text:
                text_fragments.append(part.text)
            elif part.function_call:
                text_fragments.append(part.function_call.name or "")
                text_fragments.append(str(part.function_call.args or ""))
            elif part.function_response:
                text_fragments.append(part.function_response.name or "")
                text_fragments.append(
                    str(part.function_response.response or "")
                )
            elif part.inline_data and part.inline_data.data:
                inline_image_tokens += max(
                    MIN_ESTIMATED_TOKENS_PER_INLINE_IMAGE,
                    len(part.inline_data.data)
                    // ESTIMATED_INLINE_IMAGE_BYTES_PER_TOKEN,
                )

    if llm_request.config and llm_request.config.tools:
        for tool in llm_request.config.tools:
            for declaration in (
                getattr(tool, "function_declarations", None) or []
            ):
                serialize_declaration = getattr(
                    declaration, "model_dump_json", None
                )
                text_fragments.append(
                    serialize_declaration(exclude_none=True)
                    if serialize_declaration
                    else str(declaration)
                )

    estimated_text_tokens = max(
        1, _estimate_text_tokens("\n".join(text_fragments))
    )
    return estimated_text_tokens + inline_image_tokens



def _remove_all_tools(llm_request) -> None:
    tools_dict = getattr(llm_request, "tools_dict", None)
    if tools_dict is not None:
        tools_dict.clear()
    if not llm_request.config or not llm_request.config.tools:
        return
    for tool in llm_request.config.tools:
        if tool.function_declarations:
            tool.function_declarations = []




def begin_turn_outcome_tracking() -> None:
    """Start a fresh outcome map for this turn.

    Callbacks may run in a child task. They must mutate this dict instead of
    replacing the context variable, or the parent task will not see them.
    """
    _turn_outcomes.set({})
    begin_callback_token_tracking()


def root_turn_outcome(root_agent_name: str) -> str:
    outcomes = _turn_outcomes.get()
    if not outcomes:
        return TURN_OUTCOME_COMPLETED
    return outcomes.get(root_agent_name, TURN_OUTCOME_COMPLETED)


def _record_turn_outcome(agent_name: str, outcome: str) -> None:
    outcomes = _turn_outcomes.get()
    if outcomes is None:
        outcomes = {}
        _turn_outcomes.set(outcomes)
    if outcomes.get(agent_name) in _FAILURE_TURN_OUTCOMES:
        return
    outcomes[agent_name] = outcome


def _agent_state_key(agent_name: str, name: str) -> str:
    return f"temp:{agent_name}:{name}"


def _repeated_loop_cut_index(text: str) -> int | None:
    """Return where a back-to-back repeated tail starts, or None.

    Scattered copies of a phrase, or a list of similar but not identical
    lines, are not a generated-token loop.
    """
    if len(text) < REPETITION_DETECTION_MINIMUM_CHARS:
        return None
    tail_start = max(0, len(text) - 2000)
    tail = text[tail_start:]
    earliest_cut_index = None
    for chunk_length in range(
        REPETITION_DETECTION_MINIMUM_CHUNK_CHARS,
        REPETITION_DETECTION_MAXIMUM_CHUNK_CHARS + 1,
    ):
        piece = tail[-chunk_length:]
        if len(piece.strip()) < 8:
            continue
        repeats = 0
        remaining = tail
        while remaining.endswith(piece):
            repeats += 1
            remaining = remaining[:-chunk_length]
            if repeats >= REPETITION_DETECTION_MINIMUM_REPEATS:
                cut_index = tail_start + len(remaining)
                if earliest_cut_index is None or cut_index < earliest_cut_index:
                    earliest_cut_index = cut_index
                break
    return earliest_cut_index


def _text_ends_in_a_repeated_loop(text: str) -> bool:
    return _repeated_loop_cut_index(text) is not None


def _text_with_repeated_loop_removed(text: str) -> str:
    cut_index = _repeated_loop_cut_index(text)
    if cut_index is None:
        return text
    kept_text = text[:cut_index].rstrip()
    if not kept_text:
        return _NOTICE_WHEN_REPETITIVE_RESPONSE_IS_CUT_OFF
    return f"{kept_text}\n{_NOTICE_WHEN_REPETITIVE_RESPONSE_IS_CUT_OFF}"


def _fit_text_to_token_budget(text: str, token_budget: int) -> str:
    token_budget = max(1, token_budget)
    if _estimate_text_tokens(text) <= token_budget:
        return text
    estimated_tokens = max(1, _estimate_text_tokens(text))
    keep_characters = max(1, int(len(text) * token_budget / estimated_tokens))
    if keep_characters >= len(text):
        return text
    return text[:keep_characters] + "\n[truncated to fit the model context window]"


def _shrink_text(text: str, keep_ratio: float) -> str:
    if keep_ratio >= 1:
        return text
    token_budget = max(
        MINIMUM_TOKENS_TO_KEEP_WHEN_SHRINKING_ONE_PAYLOAD,
        int(_estimate_text_tokens(text) * keep_ratio),
    )
    return _fit_text_to_token_budget(text, token_budget)


def _shrink_json_value(value, keep_ratio: float):
    if isinstance(value, str):
        return _shrink_text(value, keep_ratio)
    if isinstance(value, list):
        return [_shrink_json_value(item, keep_ratio) for item in value]
    if isinstance(value, dict):
        if _is_image_payload(value):
            return {"type": "text", "text": _PLACEHOLDER_FOR_OMITTED_IMAGE}
        return {
            key: _shrink_json_value(item, keep_ratio) for key, item in value.items()
        }
    return value


def _observation_value(value):
    """Copy used only to compare observations. Image bytes are not part of it."""
    if isinstance(value, dict):
        if _is_image_payload(value):
            return {"type": "image"}
        return {key: _observation_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_observation_value(item) for item in value]
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000]
    return value


def _observation_fingerprint(value) -> str:
    normalized = _observation_value(value)
    try:
        rendered = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        rendered = str(normalized)
    return rendered[:4000]


def _detach_part_from_session_history(part) -> None:
    """Drop this request's shared links to session-owned nested payloads.

    ADK shallow-copies each Part. function_call, function_response, and inline
    image bytes still point at the session event. Replace those fields on the
    request copy before changing them.
    """
    inline_data = part.inline_data
    if inline_data is not None and getattr(inline_data, "data", None):
        part.inline_data = None
        if part.text:
            part.text = f"{part.text}\n{_PLACEHOLDER_FOR_OMITTED_IMAGE}"
        else:
            part.text = _PLACEHOLDER_FOR_OMITTED_IMAGE
    if part.function_call is not None:
        part.function_call = part.function_call.model_copy(deep=True)
    if part.function_response is not None:
        part.function_response = part.function_response.model_copy(deep=True)


def _detach_request_parts_from_session_history(llm_request) -> None:
    for message_content in llm_request.contents or []:
        for part in message_content.parts or []:
            _detach_part_from_session_history(part)


def _latest_human_user_index(contents) -> int | None:
    latest_index = None
    for index, content in enumerate(contents or []):
        if getattr(content, "role", None) != "user":
            continue
        parts = content.parts or []
        if any(part.function_response is not None for part in parts):
            continue
        latest_index = index
    return latest_index


def _drop_history_before_latest_user_request(llm_request) -> None:
    contents = list(llm_request.contents or [])
    latest_user_index = _latest_human_user_index(contents)
    if latest_user_index is None or latest_user_index <= 0:
        return
    llm_request.contents = contents[latest_user_index:]


def _part_payload_tokens(part) -> int:
    fragments: list[str] = []
    if part.text:
        fragments.append(part.text)
    function_call = part.function_call
    if function_call is not None and function_call.args:
        fragments.append(str(function_call.args))
    function_response = part.function_response
    if function_response is not None and function_response.response is not None:
        fragments.append(str(function_response.response))
    if not fragments:
        return 0
    return _estimate_text_tokens("\n".join(fragments))


def _shrinkable_parts(llm_request, *, include_latest_user_text: bool):
    latest_user_index = _latest_human_user_index(llm_request.contents)
    for index, content in enumerate(llm_request.contents or []):
        for part in content.parts or []:
            preserves_latest_user_text = (
                not include_latest_user_text
                and index == latest_user_index
                and part.text
                and part.function_call is None
                and part.function_response is None
            )
            if preserves_latest_user_text:
                continue
            if _part_payload_tokens(part) > 0:
                yield part


def _shrink_part_payloads(part, keep_ratio: float) -> None:
    if part.text:
        part.text = _shrink_text(part.text, keep_ratio)
    function_call = part.function_call
    if function_call is not None and function_call.args:
        function_call.args = _shrink_json_value(dict(function_call.args), keep_ratio)
    function_response = part.function_response
    if function_response is not None and function_response.response is not None:
        function_response.response = _shrink_json_value(
            function_response.response, keep_ratio
        )


def _prompt_token_target(context_token_limit: int) -> int:
    response_reserve = max(
        MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE,
        context_token_limit // 5,
    )
    return max(1, context_token_limit - response_reserve)


def _shrink_parts_to_target(
    llm_request, token_target: int, *, include_latest_user_text: bool
) -> None:
    estimated_tokens = _estimate_request_token_count(llm_request)
    if estimated_tokens <= token_target:
        return
    parts = list(
        _shrinkable_parts(
            llm_request, include_latest_user_text=include_latest_user_text
        )
    )
    shrinkable_tokens = sum(_part_payload_tokens(part) for part in parts)
    if shrinkable_tokens <= 0:
        return
    overflow_tokens = estimated_tokens - token_target
    keep_ratio = max(0.0, (shrinkable_tokens - overflow_tokens) / shrinkable_tokens)
    for part in parts:
        _shrink_part_payloads(part, keep_ratio)


def _enforce_request_token_budget(llm_request, context_token_limit: int) -> None:
    """Trim the request in stages until it fits `token_target`.

    1. Drop conversation history before the latest human message.
    2. Shrink tool calls, tool results, and assistant text while keeping the
       latest human prompt intact.
    3. Shrink the latest human prompt only if the request still overflows.
    """
    token_target = _prompt_token_target(context_token_limit)
    if _estimate_request_token_count(llm_request) <= token_target:
        return
    _drop_history_before_latest_user_request(llm_request)
    if _estimate_request_token_count(llm_request) <= token_target:
        return
    _shrink_parts_to_target(
        llm_request, token_target, include_latest_user_text=False
    )
    if _estimate_request_token_count(llm_request) <= token_target:
        return
    _shrink_parts_to_target(
        llm_request, token_target, include_latest_user_text=True
    )


def _tool_observations(contents) -> list[tuple[str, str, str]]:
    observations: list[tuple[str, str, str]] = []
    pending_calls = []
    for content in contents or []:
        for part in content.parts or []:
            function_call = part.function_call
            if function_call is not None and function_call.name:
                pending_calls.append(function_call)
            function_response = part.function_response
            if function_response is None or not function_response.name:
                continue
            argument_fingerprint = ""
            if pending_calls:
                call = pending_calls.pop(0)
                if call.name == function_response.name:
                    argument_fingerprint = _observation_fingerprint(call.args)
            observations.append(
                (
                    function_response.name,
                    argument_fingerprint,
                    _observation_fingerprint(function_response.response),
                )
            )
    return observations


def _tool_observations_are_repeating(observations: list[tuple[str, str, str]]) -> bool:
    """Return True when the last N tool call/result pairs repeat a 1..4 step cycle 3 times."""
    for pattern_length in range(1, MAXIMUM_REPEATED_OBSERVATION_PATTERN_LENGTH + 1):
        window_length = pattern_length * REPEATED_OBSERVATION_RUNS_BEFORE_STALL
        if len(observations) < window_length:
            continue
        recent_observations = observations[-window_length:]
        pattern = recent_observations[:pattern_length]
        if recent_observations == pattern * REPEATED_OBSERVATION_RUNS_BEFORE_STALL:
            return True
    return False


def _context_stop_response():
    """Ends the turn without calling the model, because its context is full."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text=_NOTICE_WHEN_CONTEXT_IS_FULL)],
        )
    )


def _cap_output_tokens(
    llm_request, context_token_limit: int, estimated_prompt_tokens: int
) -> None:
    """Allow a reply as large as the context window, after the prompt."""
    remaining_tokens = context_token_limit - estimated_prompt_tokens
    output_tokens = min(
        context_token_limit,
        max(
            MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE,
            remaining_tokens - MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE,
        ),
    )
    config = llm_request.config or types.GenerateContentConfig()
    llm_request.config = config
    config.max_output_tokens = output_tokens


def _collected_response_text(llm_response) -> str:
    if not llm_response.content:
        return ""
    return "".join(
        part.text or "" for part in llm_response.content.parts or []
    )


def _answer_text(llm_response) -> str:
    if not llm_response.content:
        return ""
    return "".join(
        part.text or ""
        for part in llm_response.content.parts or []
        if part.text and not part.thought
    )


def _response_calls_a_tool(llm_response) -> bool:
    if not llm_response.content:
        return False
    return any(
        part.function_call is not None for part in llm_response.content.parts or []
    )


def _clip_unfinished_reply(text: str) -> str:
    clipped = text.strip()
    if len(clipped) > 800:
        clipped = clipped[:800].rsplit(" ", 1)[0]
    cut_index = _truncated_url_cut_index(clipped)
    if cut_index is not None:
        clipped = clipped[:cut_index].rstrip("%")
    return clipped.rstrip()


_REPLY_STOPPED_BEFORE_AN_ANSWER = (
    "The agent stopped working before it could provide an answer due to an error. The following (if available) is the recent activity of the agent (it does not constitute an answer)."
)


def _blank_partial(llm_response):
    llm_response.content = types.Content(
        role="model",
        parts=[types.Part(text="")],
    )
    return llm_response


def _stop_tools(callback_context, stop_reason: str) -> None:
    agent_name = callback_context.agent_name
    callback_context.state[_agent_state_key(agent_name, "stop_tools")] = True
    callback_context.state[_agent_state_key(agent_name, "stop_reason")] = stop_reason


def _request_has_tool_activity(llm_request) -> bool:
    for message_content in llm_request.contents or []:
        for part in message_content.parts or []:
            if part.function_call is not None or part.function_response is not None:
                return True
    return False


def _clear_stop_for_new_request(callback_context) -> None:
    """A new delegated task is not the turn that was already wrapping up."""
    agent_name = callback_context.agent_name
    callback_context.state[_agent_state_key(agent_name, "stop_tools")] = False
    callback_context.state[_agent_state_key(agent_name, "stop_reason")] = ""
    callback_context.state[_agent_state_key(agent_name, "suppress_stream")] = False
    callback_context.state[_agent_state_key(agent_name, "streamed_text")] = ""
    callback_context.state[_agent_state_key(agent_name, "streamed_answer")] = ""


def _last_tool_result_was_skipped(llm_request) -> bool:
    observations = _tool_observations(llm_request.contents)
    if not observations:
        return False
    return '"skipped": true' in observations[-1][2]


def _wrap_up_instruction(stop_reason: str | None) -> str:
    return _instruction_to_finish(stop_reason)


def _guard_model_request(callback_context, llm_request):
    """ADK `before_model_callback`: sanitize tool results, fit context budget, and stop stalled turns."""
    agent_name = callback_context.agent_name
    if not _request_has_tool_activity(llm_request):
        _clear_stop_for_new_request(callback_context)
    elif callback_context.state.get(
        _agent_state_key(agent_name, "stop_tools")
    ) and _last_tool_result_was_skipped(llm_request):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=_notice_to_finish(
                            callback_context.state.get(
                                _agent_state_key(agent_name, "stop_reason")
                            )
                        )
                    )
                ],
            )
        )
    _detach_request_parts_from_session_history(llm_request)
    prepare_model_tool_results(llm_request)
    context_token_limit = max(1, _resolve_ollama_context_length())
    _enforce_request_token_budget(llm_request, context_token_limit)
    estimated_prompt_tokens = _estimate_request_token_count(llm_request)
    callback_context.state[_agent_state_key(agent_name, "context_ratio")] = round(
        estimated_prompt_tokens / context_token_limit, 3
    )
    remaining_tokens = context_token_limit - estimated_prompt_tokens
    if (
        remaining_tokens < MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE
        and (llm_request.tools_dict or (llm_request.config and llm_request.config.tools))
    ):
        _remove_all_tools(llm_request)
        estimated_prompt_tokens = _estimate_request_token_count(llm_request)
        remaining_tokens = context_token_limit - estimated_prompt_tokens
    if remaining_tokens < MIN_REMAINING_CONTEXT_TOKENS_FOR_MODEL_RESPONSE:
        _record_turn_outcome(agent_name, TURN_OUTCOME_CONTEXT_EXHAUSTED)
        _stop_tools(callback_context, "context")
        return _context_stop_response()

    _cap_output_tokens(llm_request, context_token_limit, estimated_prompt_tokens)
    tool_observations = _tool_observations(llm_request.contents)
    stop_reason = callback_context.state.get(_agent_state_key(agent_name, "stop_reason"))
    if _tool_observations_are_repeating(tool_observations):
        stop_reason = "stalled"
        _record_turn_outcome(agent_name, TURN_OUTCOME_STALLED)
        _stop_tools(callback_context, stop_reason)
    elif tool_observations and (
        estimated_prompt_tokens / context_token_limit
        >= CONTEXT_USAGE_RATIO_THAT_STOPS_TOOL_USE
    ):
        stop_reason = stop_reason or "context"
        _stop_tools(callback_context, stop_reason)

    if callback_context.state.get(_agent_state_key(agent_name, "stop_tools")):
        _remove_all_tools(llm_request)
        llm_request.append_instructions([_wrap_up_instruction(stop_reason)])
    return None


def _guard_model_response(callback_context, llm_response):
    """ADK `after_model_callback`: salvage thought-only stops and clip token repetition loops.

    If a model finishes a turn having emitted only `<thought>` text (no visible
    answer and no tool call), its recent thinking is surfaced under a notice so
    the caller and parent agent are not left with a blank reply.
    """
    agent_name = callback_context.agent_name
    usage_metadata = llm_response.usage_metadata
    if usage_metadata and usage_metadata.prompt_token_count:
        callback_context.state[_agent_state_key(agent_name, "prompt_tokens")] = (
            usage_metadata.prompt_token_count
        )

    streamed_text_key = _agent_state_key(agent_name, "streamed_text")
    streamed_answer_key = _agent_state_key(agent_name, "streamed_answer")
    suppress_stream_key = _agent_state_key(agent_name, "suppress_stream")
    if callback_context.state.get(suppress_stream_key) and llm_response.partial:
        return _blank_partial(llm_response)

    if not llm_response.content:
        return None

    response_text = _collected_response_text(llm_response)
    answer_text = _answer_text(llm_response)
    if llm_response.partial:
        accumulated_text = str(callback_context.state.get(streamed_text_key) or "") + response_text
        callback_context.state[streamed_text_key] = accumulated_text
        if answer_text:
            callback_context.state[streamed_answer_key] = (
                str(callback_context.state.get(streamed_answer_key) or "") + answer_text
            )
    else:
        accumulated_text = (
            str(callback_context.state.get(streamed_text_key) or "") or response_text
        )
        callback_context.state[streamed_text_key] = ""
        had_answer = bool(
            answer_text.strip()
            or str(callback_context.state.get(streamed_answer_key) or "").strip()
        )
        callback_context.state[streamed_answer_key] = ""
        if not had_answer and not _response_calls_a_tool(llm_response):
            findings = _clip_unfinished_reply(accumulated_text)
            notice = (
                f"{_REPLY_STOPPED_BEFORE_AN_ANSWER}\n{findings}"
                if findings
                else _REPLY_STOPPED_BEFORE_AN_ANSWER
            )
            llm_response.content = types.Content(
                role="model",
                parts=[types.Part(text=notice)],
            )
            return llm_response

    if not _text_ends_in_a_repeated_loop(accumulated_text):
        return None

    _record_turn_outcome(agent_name, TURN_OUTCOME_REPETITION)
    _stop_tools(callback_context, "repetition")
    if llm_response.partial:
        callback_context.state[suppress_stream_key] = True
    llm_response.content = types.Content(
        role="model",
        parts=[types.Part(text=_text_with_repeated_loop_removed(accumulated_text))],
    )
    return llm_response


def _skip_tools_when_stopping(tool, args, tool_context):
    """ADK `before_tool_callback`: block tools after a stop, or expand callback tokens in `args`."""
    if tool_context.state.get(_agent_state_key(tool_context.agent_name, "stop_tools")):
        return {
            "skipped": True,
            "reason": _reason_a_tool_call_was_skipped(
                tool_context.state.get(
                    _agent_state_key(tool_context.agent_name, "stop_reason")
                )
            ),
        }
    prepare_tool_arguments(getattr(tool, "name", None), args)
    return None

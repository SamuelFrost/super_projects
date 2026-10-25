"""Turn ADK events into the text or JSON this command prints."""

import json
import sys
from typing import TextIO

from google.adk.events import Event

from lllm.output_channels import AgentOutputVisibility


class AdkEventRenderer:
    """Print the parts of an ADK event stream selected by AgentOutputVisibility."""

    def __init__(
        self,
        output_visibility: AgentOutputVisibility,
        *,
        root_agent_name: str,
        sub_agent_names: set[str],
        trace_to_stderr: bool,
        stream_output: bool,
        output_as_json: bool,
    ) -> None:
        self.output_visibility = output_visibility
        self.root_agent_name = root_agent_name
        self.sub_agent_names = sub_agent_names
        self.stream_output = stream_output and not output_as_json
        self.output_as_json = output_as_json
        self._answer_stream: TextIO = sys.stdout
        self._trace_stream: TextIO = (
            sys.stderr if trace_to_stderr and not output_as_json else sys.stdout
        )
        self._selected_output_parts_by_agent: dict[str, dict[str, list]] = {}
        self._buffered_turn_entries: list[tuple[str, str, str]] = []
        self._last_channel_by_stream: dict[TextIO, str] = {}
        self._has_pending_newline_by_stream: dict[TextIO, bool] = {}
        self._partially_streamed_agent_channels: set[tuple[str, str]] = set()
        self._agent_channels_with_printed_header: set[tuple[str, str]] = set()
        self._agents_with_recorded_answer: set[str] = set()

    def write_user_prompt(self, prompt_text: str) -> None:
        if not prompt_text or not self.output_visibility.is_enabled(
            self.root_agent_name, "prompt"
        ):
            return
        self._record_visible_prompt(self.root_agent_name, prompt_text)

    def consume(self, adk_event: Event) -> None:
        if adk_event.content is None or not adk_event.content.parts:
            return
        author_agent_name = adk_event.author or ""
        is_partial_event = bool(adk_event.partial)
        for part in adk_event.content.parts:
            if part.text:
                self._write_text(
                    author_agent_name,
                    part.thought,
                    part.text,
                    is_partial=is_partial_event,
                )
                continue
            function_call = part.function_call
            if (
                function_call is not None
                and not is_partial_event
                and function_call.name
            ):
                self.write_tool_call(
                    author_agent_name, function_call.name, function_call.args
                )
                continue
            function_response = part.function_response
            if function_response is not None and not is_partial_event:
                self.write_tool_result(
                    author_agent_name,
                    function_response.name or "tool",
                    function_response.response,
                )

    def finish(self) -> None:
        if self.output_as_json:
            _write_to_stdout(
                json.dumps(
                    self._build_selected_output_json_payload(), ensure_ascii=False
                )
                + "\n"
            )
            return
        if self.stream_output:
            for output_stream, has_pending_newline in (
                self._has_pending_newline_by_stream.items()
            ):
                if has_pending_newline:
                    output_stream.write("\n")
                    output_stream.flush()
            return
        self._write_buffered_output()

    def _get_or_create_selected_output_parts(self, agent_name: str) -> dict[str, list]:
        selected_output_parts = self._selected_output_parts_by_agent.get(agent_name)
        if selected_output_parts is None:
            selected_output_parts = {
                "thinking": [],
                "answer": [],
                "prompt": [],
                "tool_calls": [],
                "tool_results": [],
            }
            self._selected_output_parts_by_agent[agent_name] = selected_output_parts
        return selected_output_parts

    def _resolve_agent_name(self, author: str) -> str:
        return author or self.root_agent_name

    def _is_sub_agent(self, agent_name: str) -> bool:
        return agent_name in self.sub_agent_names

    def _format_prompt_block(self, agent_name: str, prompt_text: str) -> str:
        header_label = (
            agent_name
            if agent_name != self.root_agent_name
            else f"{agent_name} prompt"
        )
        prompt_body = f"\n{prompt_text}" if prompt_text else ""
        return f"[{header_label}]{prompt_body}"

    def _write_text(
        self, author: str, is_thought: bool | None, text: str, *, is_partial: bool
    ) -> None:
        agent_name = self._resolve_agent_name(author)
        channel_name = "thinking" if is_thought else "answer"
        agent_channel_key = (agent_name, channel_name)
        if (
            not is_partial
            and agent_channel_key in self._partially_streamed_agent_channels
        ):
            self._partially_streamed_agent_channels.discard(agent_channel_key)
            self._agent_channels_with_printed_header.discard(agent_channel_key)
            return
        if not text or not self.output_visibility.is_enabled(agent_name, channel_name):
            return
        if is_partial:
            self._partially_streamed_agent_channels.add(agent_channel_key)
        self._get_or_create_selected_output_parts(agent_name)[channel_name].append(text)
        if channel_name == "answer":
            self._agents_with_recorded_answer.add(agent_name)
        self._buffered_turn_entries.append((agent_name, channel_name, text))
        if not self.stream_output:
            return
        header_prefix = ""
        if (
            agent_name != self.root_agent_name
            and agent_channel_key not in self._agent_channels_with_printed_header
        ):
            header_label = "thinking" if channel_name == "thinking" else "response"
            header_prefix = f"[{agent_name} {header_label}]\n"
            self._agent_channels_with_printed_header.add(agent_channel_key)
        self._write_streaming_chunk(agent_name, channel_name, header_prefix + text)

    def _record_visible_prompt(self, agent_name: str, prompt_text: str) -> None:
        self._get_or_create_selected_output_parts(agent_name)["prompt"].append(
            prompt_text
        )
        self._buffered_turn_entries.append((agent_name, "prompt", prompt_text))
        if not self.stream_output:
            return
        rendered_prompt = self._format_prompt_block(agent_name, prompt_text) + "\n"
        self._write_streaming_chunk(agent_name, "prompt", rendered_prompt)

    def write_tool_call(
        self, author: str, tool_name: str, tool_arguments: object = None
    ) -> None:
        agent_name = self._resolve_agent_name(author)
        if self._is_sub_agent(tool_name):
            if self.output_visibility.is_enabled(tool_name, "prompt"):
                self._record_visible_prompt(
                    tool_name, _extract_sub_agent_prompt_text(tool_arguments)
                )
            return
        if not self.output_visibility.is_enabled(agent_name, "tool_calls"):
            return
        self._get_or_create_selected_output_parts(agent_name)["tool_calls"].append(
            {"name": tool_name}
        )
        rendered_tool_call = f"[{tool_name}]\n"
        self._buffered_turn_entries.append(
            (agent_name, "tool_calls", rendered_tool_call)
        )
        if self.stream_output:
            self._write_streaming_chunk(agent_name, "tool_calls", rendered_tool_call)

    def write_tool_result(
        self, author: str, tool_name: str, tool_response: object
    ) -> None:
        agent_name = self._resolve_agent_name(author)
        result_text = _extract_tool_response_text(tool_response)
        if self._is_sub_agent(tool_name):
            if tool_name in self._agents_with_recorded_answer:
                return
            if self.output_visibility.is_enabled(tool_name, "answer"):
                self._write_text(tool_name, False, result_text, is_partial=False)
                return
        if not self.output_visibility.is_enabled(agent_name, "tool_results"):
            return
        from lllm.agent import (
            _REPAIR_TRUNCATED_UTF8,
            _repair_truncated_utf8_in_value,
        )

        repaired_response, repaired_url_count = _repair_truncated_utf8_in_value(
            tool_response
        )
        if repaired_url_count:
            tool_name = f"{tool_name} {_REPAIR_TRUNCATED_UTF8} {repaired_url_count}"
            result_text = _extract_tool_response_text(repaired_response)
        self._get_or_create_selected_output_parts(agent_name)["tool_results"].append(
            {"name": tool_name, "text": result_text}
        )
        rendered_tool_result = f"[{tool_name} result]\n{result_text}\n"
        self._buffered_turn_entries.append(
            (agent_name, "tool_results", rendered_tool_result)
        )
        if self.stream_output:
            self._write_streaming_chunk(
                agent_name, "tool_results", rendered_tool_result
            )

    def _build_selected_output_json_payload(self) -> dict[str, object]:
        selected_output_payload: dict[str, object] = {}
        for (
            agent_name,
            selected_output_parts,
        ) in self._selected_output_parts_by_agent.items():
            selected_agent_payload: dict[str, object] = {}
            if selected_output_parts["thinking"]:
                selected_agent_payload["thinking"] = "".join(
                    selected_output_parts["thinking"]
                )
            if selected_output_parts["answer"]:
                selected_agent_payload["answer"] = "".join(
                    selected_output_parts["answer"]
                )
            if selected_output_parts["prompt"]:
                selected_agent_payload["prompt"] = "\n".join(
                    selected_output_parts["prompt"]
                )
            if selected_output_parts["tool_calls"]:
                selected_agent_payload["tool_calls"] = selected_output_parts["tool_calls"]
            if selected_output_parts["tool_results"]:
                selected_agent_payload["tool_results"] = selected_output_parts["tool_results"]
            if selected_agent_payload:
                selected_output_payload[agent_name] = selected_agent_payload
        return selected_output_payload

    def _format_buffered_entry(
        self, agent_name: str, channel_name: str, text: str
    ) -> tuple[str, str]:
        if agent_name == self.root_agent_name and channel_name == "answer":
            return "answer", text
        if channel_name == "answer":
            return "trace", f"[{agent_name} response]\n{text}"
        if channel_name == "prompt":
            return "trace", self._format_prompt_block(agent_name, text)
        if channel_name == "thinking" and agent_name != self.root_agent_name:
            return "trace", f"[{agent_name} thinking]\n{text}"
        return "trace", text

    def _write_buffered_output(self) -> None:
        answer_parts: list[str] = []
        trace_parts: list[str] = []
        for agent_name, channel_name, text in self._buffered_turn_entries:
            stream_name, rendered_entry = self._format_buffered_entry(
                agent_name, channel_name, text
            )
            if stream_name == "answer":
                answer_parts.append(rendered_entry)
            elif rendered_entry:
                trace_parts.append(rendered_entry)
        answer_text = "".join(answer_parts).rstrip("\n")
        trace_text = "".join(trace_parts).strip("\n")
        if self._trace_stream is self._answer_stream:
            output_blocks = [block for block in (trace_text, answer_text) if block]
            if output_blocks:
                _write_to_stdout("\n".join(output_blocks) + "\n")
            return
        if trace_text:
            self._trace_stream.write(trace_text + "\n")
            self._trace_stream.flush()
        if answer_text:
            _write_to_stdout(answer_text + "\n")

    def _write_streaming_chunk(
        self, agent_name: str, channel_name: str, text_chunk: str
    ) -> None:
        stream_channel_key = f"{agent_name}:{channel_name}"
        output_stream = (
            self._answer_stream
            if agent_name == self.root_agent_name and channel_name == "answer"
            else self._trace_stream
        )
        previous_channel = self._last_channel_by_stream.get(output_stream)
        if previous_channel not in (
            None,
            stream_channel_key,
        ) and self._has_pending_newline_by_stream.get(output_stream):
            output_stream.write("\n")
            self._has_pending_newline_by_stream[output_stream] = False
        self._last_channel_by_stream[output_stream] = stream_channel_key
        output_stream.write(text_chunk)
        output_stream.flush()
        self._has_pending_newline_by_stream[output_stream] = not text_chunk.endswith(
            "\n"
        )


def _write_to_stdout(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _extract_sub_agent_prompt_text(tool_arguments: object) -> str:
    if tool_arguments is None:
        return ""
    request_text = None
    if isinstance(tool_arguments, dict):
        request_text = tool_arguments.get("request")
    elif hasattr(tool_arguments, "get"):
        request_text = tool_arguments.get("request")
    if isinstance(request_text, str) and request_text:
        return request_text
    try:
        tool_arguments_as_dict = dict(tool_arguments)
    except (TypeError, ValueError):
        return str(tool_arguments)
    if not tool_arguments_as_dict:
        return ""
    return json.dumps(tool_arguments_as_dict, ensure_ascii=False, default=str)


def _extract_tool_response_text(tool_response: object) -> str:
    if not isinstance(tool_response, dict):
        return "" if tool_response is None else str(tool_response)
    content = tool_response.get("content")
    if isinstance(content, list):
        text_items = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("text")
        ]
        if text_items:
            return "\n".join(text_items)
    if isinstance(content, str):
        return content
    result = tool_response.get("result")
    if isinstance(result, str):
        return result
    return str(tool_response)

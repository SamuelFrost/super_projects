"""Stream the local model's reply as it is generated.

`adk run` waits for a finished response. This uses the same agent with
server-sent streaming, and writes each selected text delta as it arrives.

With no channel options, thinking, the answer, and tool names are shown.
Pass one or more of --thinking, --answer, --tools, or --tool-results to
show only those. Tool results stay off unless requested: they are large
and crowd an orchestrating agent's context.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import TextIO

import readline  # noqa: F401  GNU readline for input()

from google.adk.agents.run_config import RunConfig
from google.adk.agents._streaming_mode import StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types

from lllm.agent import app

STREAMING_RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)


@dataclass
class OutputChannels:
    thinking: bool
    answer: bool
    tools: bool
    tool_results: bool

    @classmethod
    def from_parsed_arguments(cls, parsed_args: argparse.Namespace) -> "OutputChannels":
        if (
            parsed_args.thinking
            or parsed_args.answer
            or parsed_args.tools
            or parsed_args.tool_results
        ):
            return cls(
                thinking=parsed_args.thinking,
                answer=parsed_args.answer,
                tools=parsed_args.tools,
                tool_results=parsed_args.tool_results,
            )
        return cls(thinking=True, answer=True, tools=True, tool_results=False)

    def includes_text_part(self, is_thought: bool | None) -> bool:
        if is_thought:
            return self.thinking
        return self.answer


class TurnWriter:
    def __init__(
        self,
        channels: OutputChannels,
        *,
        trace_to_stderr: bool,
        stream_output: bool,
        output_as_json: bool,
    ) -> None:
        self.channels = channels
        self.stream_output = stream_output and not output_as_json
        self.output_as_json = output_as_json
        self._answer_stream: TextIO = sys.stdout
        self._trace_stream: TextIO = (
            sys.stderr if trace_to_stderr and not output_as_json else sys.stdout
        )
        self._collected_parts_by_channel: dict[str, list] = {
            "thinking": [],
            "answer": [],
            "tools": [],
            "tool_results": [],
        }
        self._last_channel_by_stream: dict[TextIO, str] = {}
        self._has_pending_newline_by_stream: dict[TextIO, bool] = {}

    def write_text_delta(self, is_thought: bool | None, text_delta: str) -> None:
        if not text_delta or not self.channels.includes_text_part(is_thought):
            return
        channel_name = "thinking" if is_thought else "answer"
        self._collected_parts_by_channel[channel_name].append(text_delta)
        if self.stream_output:
            self._write_streaming_chunk(channel_name, text_delta)

    def write_tool_call(self, tool_name: str) -> None:
        if not self.channels.tools:
            return
        self._collected_parts_by_channel["tools"].append(tool_name)
        if self.stream_output:
            self._write_streaming_chunk("tools", f"[{tool_name}]\n")

    def write_tool_result(self, tool_name: str, tool_response: object) -> None:
        if not self.channels.tool_results:
            return
        result_text = _extract_tool_result_text(tool_response)
        self._collected_parts_by_channel["tool_results"].append(
            {"name": tool_name, "text": result_text}
        )
        if self.stream_output:
            self._write_streaming_chunk(
                "tool_results", f"[{tool_name} result]\n{result_text}\n"
            )

    def finish_turn(self) -> None:
        if self.output_as_json:
            _write_to_stdout(
                json.dumps(self._build_json_payload(), ensure_ascii=False) + "\n"
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

    def _build_json_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.channels.thinking:
            payload["thinking"] = "".join(self._collected_parts_by_channel["thinking"])
        if self.channels.answer:
            payload["answer"] = "".join(self._collected_parts_by_channel["answer"])
        if self.channels.tools:
            payload["tools"] = self._collected_parts_by_channel["tools"]
        if self.channels.tool_results:
            payload["tool_results"] = self._collected_parts_by_channel["tool_results"]
        return payload

    def _write_buffered_output(self) -> None:
        trace_blocks: list[str] = []
        if self.channels.thinking and self._collected_parts_by_channel["thinking"]:
            trace_blocks.append(
                "".join(self._collected_parts_by_channel["thinking"]).rstrip("\n")
            )
        if self.channels.tools and self._collected_parts_by_channel["tools"]:
            trace_blocks.append(
                "\n".join(
                    f"[{tool_name}]"
                    for tool_name in self._collected_parts_by_channel["tools"]
                )
            )
        if (
            self.channels.tool_results
            and self._collected_parts_by_channel["tool_results"]
        ):
            trace_blocks.append(
                "\n".join(
                    f"[{tool_result['name']} result]\n{tool_result['text']}"
                    for tool_result in self._collected_parts_by_channel["tool_results"]
                )
            )
        answer_text = ""
        if self.channels.answer and self._collected_parts_by_channel["answer"]:
            answer_text = "".join(self._collected_parts_by_channel["answer"]).rstrip(
                "\n"
            )
        if self._trace_stream is self._answer_stream:
            output_blocks = [*trace_blocks, answer_text] if answer_text else trace_blocks
            if output_blocks:
                _write_to_stdout("\n".join(output_blocks) + "\n")
            return
        if trace_blocks:
            self._trace_stream.write("\n".join(trace_blocks) + "\n")
            self._trace_stream.flush()
        if answer_text:
            _write_to_stdout(answer_text + "\n")

    def _write_streaming_chunk(self, channel_name: str, text_chunk: str) -> None:
        output_stream = (
            self._answer_stream if channel_name == "answer" else self._trace_stream
        )
        previous_channel = self._last_channel_by_stream.get(output_stream)
        if previous_channel not in (
            None,
            channel_name,
        ) and self._has_pending_newline_by_stream.get(output_stream):
            output_stream.write("\n")
            self._has_pending_newline_by_stream[output_stream] = False
        self._last_channel_by_stream[output_stream] = channel_name
        output_stream.write(text_chunk)
        output_stream.flush()
        self._has_pending_newline_by_stream[output_stream] = not text_chunk.endswith(
            "\n"
        )


async def _await_if_coroutine(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


def _write_to_stdout(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _extract_tool_result_text(tool_response: object) -> str:
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
    return str(tool_response)


async def run_turn(
    runner: InMemoryRunner,
    session_id: str,
    user_id: str,
    prompt_text: str,
    channels: OutputChannels,
    *,
    trace_to_stderr: bool = False,
    stream_output: bool = True,
    output_as_json: bool = False,
) -> None:
    writer = TurnWriter(
        channels,
        trace_to_stderr=trace_to_stderr,
        stream_output=stream_output,
        output_as_json=output_as_json,
    )
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt_text)]),
        run_config=STREAMING_RUN_CONFIG,
    ):
        content = event.content
        if content is None or not content.parts:
            continue
        for part in content.parts:
            if part.text and event.partial:
                writer.write_text_delta(part.thought, part.text)
                continue
            function_call = part.function_call
            if function_call is not None and not event.partial and function_call.name:
                writer.write_tool_call(function_call.name)
                continue
            function_response = part.function_response
            if function_response is not None and not event.partial:
                writer.write_tool_result(
                    function_response.name or "tool", function_response.response
                )
    writer.finish_turn()


async def _create_session(runner: InMemoryRunner, user_id: str):
    return await _await_if_coroutine(
        runner.session_service.create_session(app_name=app.name, user_id=user_id)
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lllm",
        description=(
            "Talk to the local model. Channel options choose what is printed. "
            "With none of them, thinking, the answer, and tool names are shown."
        ),
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Print the model's thinking. Omit the other channel options to keep the default.",
    )
    parser.add_argument(
        "--answer",
        action="store_true",
        help="Print only the reply when this is the only channel option. Use this when another agent is calling lllm.",
    )
    parser.add_argument(
        "--tools",
        action="store_true",
        help="Print the name of each tool call.",
    )
    parser.add_argument(
        "--tool-results",
        action="store_true",
        help="Print each tool result. These are large; leave this off for an orchestrating agent.",
    )
    parser.add_argument(
        "--stderr",
        action="store_true",
        help="Send thinking and tool lines to stderr. The answer stays on stdout.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Print the turn when it finishes, instead of streaming characters.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON object on stdout for the selected channels.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        metavar="SECONDS",
        help="Stop the turn after this many seconds.",
    )
    parser.add_argument(
        "query", nargs="*", help="One turn. With no query, the session stays open."
    )
    return parser


def _clear_task_cancellation() -> None:
    current_task = asyncio.current_task()
    if current_task is None:
        return
    while current_task.cancelling():
        current_task.uncancel()


async def main() -> None:
    parsed_args = _build_argument_parser().parse_args()
    channels = OutputChannels.from_parsed_arguments(parsed_args)
    user_id = "user"
    runner = InMemoryRunner(app=app)
    session = await _create_session(runner, user_id)
    interrupted = False
    try:
        async def run_single_turn(prompt_text: str) -> None:
            turn_coroutine = run_turn(
                runner,
                session.id,
                user_id,
                prompt_text,
                channels,
                trace_to_stderr=parsed_args.stderr,
                stream_output=not parsed_args.no_stream,
                output_as_json=parsed_args.json,
            )
            if parsed_args.timeout is None:
                await turn_coroutine
                return
            try:
                await asyncio.wait_for(turn_coroutine, parsed_args.timeout)
            except asyncio.TimeoutError:
                print(
                    f"lllm: timed out after {parsed_args.timeout:g}s",
                    file=sys.stderr,
                )
                raise SystemExit(124) from None

        if parsed_args.query:
            await run_single_turn(" ".join(parsed_args.query))
            return
        while True:
            try:
                user_input = input("> ")
            except (EOFError, KeyboardInterrupt):
                _write_to_stdout("\n")
                return
            if user_input.strip().lower() in {"exit", "quit"}:
                return
            if not user_input.strip():
                continue
            await run_single_turn(user_input)
    except asyncio.CancelledError:
        interrupted = True
    finally:
        # Ctrl+C cancels this task. Clear that so closing the runner can finish.
        _clear_task_cancellation()
        await _await_if_coroutine(runner.close())
    if interrupted:
        _write_to_stdout("\n")
        print("lllm: interrupted", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _write_to_stdout("\n")
        print("lllm: interrupted", file=sys.stderr)
        raise SystemExit(130) from None

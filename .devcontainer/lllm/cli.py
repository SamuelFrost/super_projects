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

import readline  # noqa: F401  GNU readline for input()

from google.adk.agents.run_config import RunConfig
from google.adk.agents._streaming_mode import StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types

from lllm.agent import app

_RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)


@dataclass
class OutputChannels:
    thinking: bool
    answer: bool
    tools: bool
    tool_results: bool

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "OutputChannels":
        if args.thinking or args.answer or args.tools or args.tool_results:
            return cls(args.thinking, args.answer, args.tools, args.tool_results)
        return cls(thinking=True, answer=True, tools=True, tool_results=False)

    def allows_text(self, thought: bool | None) -> bool:
        if thought:
            return self.thinking
        return self.answer


class TurnWriter:
    def __init__(
        self,
        channels: OutputChannels,
        *,
        trace_to_stderr: bool,
        stream: bool,
        as_json: bool,
    ) -> None:
        self.channels = channels
        self.stream = stream and not as_json
        self.as_json = as_json
        self._answer_file = sys.stdout
        self._trace_file = sys.stderr if trace_to_stderr and not as_json else sys.stdout
        self._parts: dict[str, list] = {
            "thinking": [],
            "answer": [],
            "tools": [],
            "tool_results": [],
        }
        self._last_channel: dict[object, str] = {}
        self._pending_newline: dict[object, bool] = {}

    def text(self, thought: bool | None, value: str) -> None:
        if not value or not self.channels.allows_text(thought):
            return
        channel = "thinking" if thought else "answer"
        self._parts[channel].append(value)
        if self.stream:
            self._emit(channel, value)

    def tool(self, name: str) -> None:
        if not self.channels.tools:
            return
        self._parts["tools"].append(name)
        if self.stream:
            self._emit("tools", f"[{name}]\n")

    def tool_result(self, name: str, response: object) -> None:
        if not self.channels.tool_results:
            return
        text = _result_text(response)
        self._parts["tool_results"].append({"name": name, "text": text})
        if self.stream:
            self._emit("tool_results", f"[{name} result]\n{text}\n")

    def finish(self) -> None:
        if self.as_json:
            _write(json.dumps(self._payload(), ensure_ascii=False) + "\n")
            return
        if self.stream:
            for stream, pending in self._pending_newline.items():
                if pending:
                    stream.write("\n")
                    stream.flush()
            return
        self._write_buffered()

    def _payload(self) -> dict:
        payload = {}
        if self.channels.thinking:
            payload["thinking"] = "".join(self._parts["thinking"])
        if self.channels.answer:
            payload["answer"] = "".join(self._parts["answer"])
        if self.channels.tools:
            payload["tools"] = self._parts["tools"]
        if self.channels.tool_results:
            payload["tool_results"] = self._parts["tool_results"]
        return payload

    def _write_buffered(self) -> None:
        trace = []
        if self.channels.thinking and self._parts["thinking"]:
            trace.append("".join(self._parts["thinking"]).rstrip("\n"))
        if self.channels.tools and self._parts["tools"]:
            trace.append("\n".join(f"[{name}]" for name in self._parts["tools"]))
        if self.channels.tool_results and self._parts["tool_results"]:
            trace.append(
                "\n".join(
                    f"[{item['name']} result]\n{item['text']}"
                    for item in self._parts["tool_results"]
                )
            )
        answer = ""
        if self.channels.answer and self._parts["answer"]:
            answer = "".join(self._parts["answer"]).rstrip("\n")
        if self._trace_file is self._answer_file:
            blocks = [*trace, answer] if answer else trace
            if blocks:
                _write("\n".join(blocks) + "\n")
            return
        if trace:
            self._trace_file.write("\n".join(trace) + "\n")
            self._trace_file.flush()
        if answer:
            _write(answer + "\n")

    def _emit(self, channel: str, text: str) -> None:
        stream = self._answer_file if channel == "answer" else self._trace_file
        previous = self._last_channel.get(stream)
        if previous not in (None, channel) and self._pending_newline.get(stream):
            stream.write("\n")
            self._pending_newline[stream] = False
        self._last_channel[stream] = channel
        stream.write(text)
        stream.flush()
        self._pending_newline[stream] = not text.endswith("\n")


async def _resolve(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


def _write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _result_text(response: object) -> str:
    if not isinstance(response, dict):
        return "" if response is None else str(response)
    content = response.get("content")
    if isinstance(content, list):
        texts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("text")
        ]
        if texts:
            return "\n".join(texts)
    if isinstance(content, str):
        return content
    return str(response)


async def run_turn(
    runner: InMemoryRunner,
    session_id: str,
    user_id: str,
    text: str,
    channels: OutputChannels,
    *,
    trace_to_stderr: bool = False,
    stream: bool = True,
    as_json: bool = False,
) -> None:
    writer = TurnWriter(
        channels,
        trace_to_stderr=trace_to_stderr,
        stream=stream,
        as_json=as_json,
    )
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
        run_config=_RUN_CONFIG,
    ):
        content = event.content
        if content is None or not content.parts:
            continue
        for part in content.parts:
            if part.text and event.partial:
                writer.text(part.thought, part.text)
                continue
            call = part.function_call
            if call is not None and not event.partial and call.name:
                writer.tool(call.name)
                continue
            response = part.function_response
            if response is not None and not event.partial:
                writer.tool_result(response.name or "tool", response.response)
    writer.finish()


async def _session(runner: InMemoryRunner, user_id: str):
    return await _resolve(
        runner.session_service.create_session(app_name=app.name, user_id=user_id)
    )


def _parser() -> argparse.ArgumentParser:
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
    parser.add_argument("query", nargs="*", help="One turn. With no query, the session stays open.")
    return parser


async def main() -> None:
    args = _parser().parse_args()
    channels = OutputChannels.from_args(args)
    user_id = "user"
    runner = InMemoryRunner(app=app)
    session = await _session(runner, user_id)
    try:
        async def one_turn(text: str) -> None:
            turn = run_turn(
                runner,
                session.id,
                user_id,
                text,
                channels,
                trace_to_stderr=args.stderr,
                stream=not args.no_stream,
                as_json=args.json,
            )
            if args.timeout is None:
                await turn
                return
            try:
                await asyncio.wait_for(turn, args.timeout)
            except asyncio.TimeoutError:
                print(f"lllm: timed out after {args.timeout:g}s", file=sys.stderr)
                raise SystemExit(124) from None

        if args.query:
            await one_turn(" ".join(args.query))
            return
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                _write("\n")
                return
            if line.strip().lower() in {"exit", "quit"}:
                return
            if not line.strip():
                continue
            await one_turn(line)
    finally:
        await _resolve(runner.close())


if __name__ == "__main__":
    asyncio.run(main())

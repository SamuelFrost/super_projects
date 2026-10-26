"""Command-line session for the local ADK app.

The agents live in lllm.agent. Whether a turn finished lives in lllm.runtime_modifiers.turn_guards.
This module parses arguments, preloads Ollama, and prints the selected events.
lllm.adk_runtime is what actually calls ADK.
"""

import argparse
import asyncio
import sys

import readline  # noqa: F401  GNU readline for input()

from google.adk.agents.run_config import RunConfig, StreamingMode

from lllm.adk_runtime import AdkSession
from lllm.agent import agents_in_composition_order, app_for_agent
from lllm.runtime_modifiers.turn_guards import (
    TURN_OUTCOME_CONTEXT_EXHAUSTED,
    TURN_OUTCOME_REPETITION,
    TURN_OUTCOME_STALLED,
    begin_turn_outcome_tracking,
    root_turn_outcome,
)
from lllm.ollama import ensure_model_loaded
from lllm.output_channels import (
    AgentOutputVisibility,
    collect_sub_agent_names,
    parse_output_channels_argument,
)
from lllm.cli.output_writer import AdkEventRenderer

ADK_SSE_RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)
INCOMPLETE_TURN_EXIT_CODE = 75
_INCOMPLETE_TURN_MESSAGES = {
    TURN_OUTCOME_CONTEXT_EXHAUSTED: (
        "lllm: stopped because the context window was full"
    ),
    TURN_OUTCOME_REPETITION: "lllm: stopped because the reply repeated itself",
    TURN_OUTCOME_STALLED: (
        "lllm: stopped because the same action repeated without new information"
    ),
}


def incomplete_turn_message(outcome: str) -> str | None:
    return _INCOMPLETE_TURN_MESSAGES.get(outcome)


def _build_argument_parser() -> argparse.ArgumentParser:
    composed_agent_names = [agent.name for agent in agents_in_composition_order()]
    parser = argparse.ArgumentParser(
        prog="lllm",
        description=(
            "Talk to the local model. --outputChannels is a JSON object "
            "choosing what each author prints. Omitting it shows thinking, "
            "the answer, and tool names, plus each sub-agent request. Tool "
            "results stay off."
        ),
    )
    parser.add_argument(
        "--agent",
        choices=composed_agent_names,
        help=(
            "Agent from the composed tree to talk to. "
            f"The default is {composed_agent_names[0]}."
        ),
    )
    parser.add_argument(
        "--outputChannels",
        type=parse_output_channels_argument,
        metavar="JSON",
        help=(
            "JSON object with defaults, sub_agent_defaults, and "
            "agent_overrides. Information keys are thinking, answer, "
            "tool_calls, tool_results, and prompt. Values are booleans. "
            "Example: "
            '\'{"sub_agent_defaults":{"tool_calls":false},'
            '"agent_overrides":[{"target_agents":["files_agent"],'
            '"tool_results":true}]}\''
        ),
    )
    parser.add_argument(
        "--stderr",
        action="store_true",
        help=(
            "Send thinking, tool lines, and sub-agent requests and replies "
            "to stderr. The answer stays on stdout."
        ),
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


def _write_to_stdout(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _clear_task_cancellation() -> None:
    current_task = asyncio.current_task()
    if current_task is None:
        return
    while current_task.cancelling():
        current_task.uncancel()


async def run_prompt_turn(
    session: AdkSession,
    selected_app,
    prompt_text: str,
    output_visibility: AgentOutputVisibility,
    *,
    trace_to_stderr: bool,
    stream_output: bool,
    output_as_json: bool,
) -> str:
    begin_turn_outcome_tracking()
    selected_root = selected_app.root_agent
    renderer = AdkEventRenderer(
        output_visibility,
        root_agent_name=selected_root.name,
        sub_agent_names=collect_sub_agent_names(selected_root),
        trace_to_stderr=trace_to_stderr,
        stream_output=stream_output,
        output_as_json=output_as_json,
    )
    renderer.write_user_prompt(prompt_text)
    async for adk_event in session.stream_events(prompt_text, ADK_SSE_RUN_CONFIG):
        renderer.consume(adk_event)
    renderer.finish()
    return root_turn_outcome(selected_root.name)


async def main() -> None:
    parsed_args = _build_argument_parser().parse_args()
    ensure_model_loaded()
    output_visibility = AgentOutputVisibility.from_arguments(parsed_args)
    selected_app = app_for_agent(parsed_args.agent)
    interrupted = False
    session = await AdkSession.create(selected_app, user_id="user")
    try:

        async def run_one_prompt_turn(prompt_text: str) -> None:
            prompt_turn_coroutine = run_prompt_turn(
                session,
                selected_app,
                prompt_text,
                output_visibility,
                trace_to_stderr=parsed_args.stderr,
                stream_output=not parsed_args.no_stream,
                output_as_json=parsed_args.json,
            )
            try:
                turn_outcome = await asyncio.wait_for(
                    prompt_turn_coroutine, parsed_args.timeout
                )
            except asyncio.TimeoutError:
                print(
                    f"lllm: timed out after {parsed_args.timeout:g}s",
                    file=sys.stderr,
                )
                raise SystemExit(124) from None
            incomplete_message = incomplete_turn_message(turn_outcome)
            if incomplete_message:
                print(incomplete_message, file=sys.stderr)
                raise SystemExit(INCOMPLETE_TURN_EXIT_CODE)

        if parsed_args.query:
            await run_one_prompt_turn(" ".join(parsed_args.query))
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
            await run_one_prompt_turn(user_input)
    except asyncio.CancelledError:
        interrupted = True
    finally:
        # Ctrl+C cancels this task. Clear that so closing the runner can finish.
        _clear_task_cancellation()
        await session.close()
    if interrupted:
        _write_to_stdout("\n")
        print("lllm: interrupted", file=sys.stderr)
        raise SystemExit(130)


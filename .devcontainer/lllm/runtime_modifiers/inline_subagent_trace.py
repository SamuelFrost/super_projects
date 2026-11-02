"""Show a delegated sub-agent's events in the main web transcript.

`single_turn` publishes that work on a child branch. The dev UI then files
those events into a side panel, so the thinking and tool calls disappear from
the chat the caller is watching. A child branch is cleared before the event is
stored. An event that is already on the invocation's own branch stays there,
which leaves a direct `lllm --agent` session unchanged.
"""

from google.adk.events.event import Event
from google.adk.plugins.base_plugin import BasePlugin

from google.adk.events._branch_path import _BranchPath


def _branch_is_child_of_invocation(
    event_branch: str | None, invocation_branch: str | None
) -> bool:
    if not event_branch:
        return False
    event_path = _BranchPath.from_string(event_branch)
    invocation_path = _BranchPath.from_string(invocation_branch)
    if not invocation_path.segments:
        return True
    return event_path.is_descendant_of(invocation_path)


class InlineSubagentTracePlugin(BasePlugin):
    """Persist delegated sub-agent events on the main transcript branch."""

    def __init__(self) -> None:
        super().__init__(name="inline_subagent_trace")

    async def on_event_callback(
        self, *, invocation_context, event: Event
    ) -> Event | None:
        if not _branch_is_child_of_invocation(
            event.branch, getattr(invocation_context, "branch", None)
        ):
            return None
        return event.model_copy(update={"branch": None})

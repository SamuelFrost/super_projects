"""Run the local ADK app and yield its events.

This module starts a session and sends one prompt. It does not decide which
events are printed.
"""

from collections.abc import AsyncIterator

from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types


class AdkSession:
    """One conversation with an ADK app."""

    def __init__(
        self,
        runner: InMemoryRunner,
        session,
        user_id: str,
    ) -> None:
        self.runner = runner
        self.session = session
        self.user_id = user_id

    @classmethod
    async def create(cls, app: App, user_id: str) -> "AdkSession":
        runner = InMemoryRunner(app=app)
        session = await runner.session_service.create_session(
            app_name=app.name,
            user_id=user_id,
        )
        return cls(runner, session, user_id)

    def stream_events(
        self,
        prompt: str,
        run_config: RunConfig,
    ) -> AsyncIterator[Event]:
        """Send one prompt. Iterating this is what makes ADK run."""
        return self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session.id,
            new_message=types.UserContent(prompt),
            run_config=run_config,
        )

    async def close(self) -> None:
        await self.runner.close()

    async def __aenter__(self) -> "AdkSession":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

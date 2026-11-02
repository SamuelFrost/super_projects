"""Run the local ADK app and yield its events.

This module starts or resumes a session in the same SQLite database `lllm web`
uses, then sends one prompt. It does not decide which events are printed.
"""

from collections.abc import AsyncIterator
from pathlib import Path

from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

from lllm.session_store import UnknownSessionError
from lllm.tools.callback_tokens import (
    bind_callback_tokens_to_session,
    use_callback_token_database,
)


class AdkSession:
    """One conversation with an ADK app."""

    def __init__(
        self,
        runner,
        session,
        user_id: str,
    ) -> None:
        self.runner = runner
        self.session = session
        self.user_id = user_id

    @classmethod
    async def open(
        cls,
        app: App,
        user_id: str,
        *,
        session_db: Path,
        session_id: str | None = None,
    ) -> "AdkSession":
        """Create a session, or resume one already stored in `session_db`."""
        session_db.parent.mkdir(parents=True, exist_ok=True)
        use_callback_token_database(session_db)
        session_service = SqliteSessionService(str(session_db))
        runner = Runner(app=app, session_service=session_service)
        if session_id:
            session = await session_service.get_session(
                app_name=app.name,
                user_id=user_id,
                session_id=session_id,
            )
            if session is None:
                await session_service.close()
                raise UnknownSessionError(session_id)
        else:
            session = await session_service.create_session(
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
        bind_callback_tokens_to_session(self.session.id)
        return self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session.id,
            new_message=types.UserContent(prompt),
            run_config=run_config,
        )

    async def close(self) -> None:
        await self.runner.close()
        session_service = getattr(self.runner, "session_service", None)
        close_session_service = getattr(session_service, "close", None)
        if close_session_service is not None:
            await close_session_service()

    async def __aenter__(self) -> "AdkSession":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

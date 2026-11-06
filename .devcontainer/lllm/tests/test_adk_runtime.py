import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from google.adk.events.event import Event
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

from lllm.adk_runtime import AdkSession
from lllm.agent import app, app_for_agent
from lllm.cli.cli_config import ADK_SSE_RUN_CONFIG
from lllm.session_store import UnknownSessionError
from lllm.session_transcript import session_transcript_path


class AdkRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_events_sends_one_prompt_to_the_runner(self):
        runner = _FakeRunner()
        session = AdkSession(runner, SimpleNamespace(id="session-1"), "user")
        streamed = [event async for event in session.stream_events("hello", ADK_SSE_RUN_CONFIG)]
        self.assertEqual(streamed, ["event"])
        self.assertEqual(runner.calls[0]["user_id"], "user")
        self.assertEqual(runner.calls[0]["session_id"], "session-1")
        self.assertEqual(runner.calls[0]["run_config"], ADK_SSE_RUN_CONFIG)
        self.assertIsInstance(runner.calls[0]["new_message"], types.Content)
        self.assertEqual(runner.calls[0]["new_message"].parts[0].text, "hello")

    async def test_close_closes_the_runner(self):
        runner = _FakeRunner()
        session = AdkSession(runner, SimpleNamespace(id="session-1"), "user")
        await session.close()
        self.assertTrue(runner.closed)

    async def test_open_resumes_events_from_the_session_database(self):
        with tempfile.TemporaryDirectory() as directory:
            session_db = Path(directory) / "session.db"
            first = await AdkSession.open(app, "user", session_db=session_db)
            await first.runner.session_service.append_event(
                first.session,
                Event(
                    author="user",
                    content=types.Content(
                        role="user", parts=[types.Part(text="remember this page")]
                    ),
                ),
            )
            session_id = first.session.id
            await first.close()

            second = await AdkSession.open(
                app, "user", session_db=session_db, session_id=session_id
            )
            stored = await second.runner.session_service.get_session(
                app_name=app.name,
                user_id="user",
                session_id=session_id,
            )
            texts = [
                part.text
                for event in stored.events
                for part in (event.content.parts if event.content else [])
                if part.text
            ]
            self.assertIn("remember this page", texts)
            await second.close()

    async def test_open_rejects_an_unknown_session(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UnknownSessionError) as raised:
                await AdkSession.open(
                    app,
                    "user",
                    session_db=Path(directory) / "session.db",
                    session_id="missing-session",
                )
        self.assertEqual(raised.exception.session_id, "missing-session")

    async def test_open_rejects_a_session_from_another_app(self):
        with tempfile.TemporaryDirectory() as directory:
            session_db = Path(directory) / "session.db"
            first = await AdkSession.open(app, "user", session_db=session_db)
            session_id = first.session.id
            await first.close()
            with self.assertRaises(UnknownSessionError) as raised:
                await AdkSession.open(
                    app_for_agent("browser_agent"),
                    "user",
                    session_db=session_db,
                    session_id=session_id,
                )
        self.assertEqual(raised.exception.session_id, session_id)

    async def test_cli_and_web_events_share_one_session_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            session_db = Path(directory) / "session.db"
            log_dir = Path(directory) / "journal"
            first = await AdkSession.open(
                app,
                "user",
                session_db=session_db,
                transcript_dir=log_dir,
            )
            await first.runner.session_service.append_event(
                first.session,
                _user_event("hi"),
            )
            web_service = SqliteSessionService(str(session_db))
            web_service._lllm_transcript_dir = log_dir
            stored = await web_service.get_session(
                app_name=app.name,
                user_id="user",
                session_id=first.session.id,
            )
            await web_service.append_event(stored, _user_event("from the web"))
            transcript = session_transcript_path(
                log_dir, app.name, first.session.id
            ).read_text(encoding="utf-8")
            self.assertIn("[user]\nhi", transcript)
            self.assertIn("[user]\nfrom the web", transcript)
            self.assertEqual(transcript.count("[user]"), 2)
            await web_service.close()
            await first.close()


def _user_event(text: str) -> Event:
    return Event(
        author="user",
        content=types.Content(role="user", parts=[types.Part(text=text)]),
    )


class _FakeRunner:
    def __init__(self):
        self.calls = []
        self.closed = False

    def run_async(self, **kwargs):
        self.calls.append(kwargs)

        async def generate():
            yield "event"

        return generate()

    async def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()

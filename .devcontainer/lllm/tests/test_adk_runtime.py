import unittest
from types import SimpleNamespace

from google.genai import types

from lllm.adk_runtime import AdkSession
from lllm.cli.cli_config import ADK_SSE_RUN_CONFIG


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

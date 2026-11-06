import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lllm.agent import app, app_for_agent, named_apps, prefixed_app_name
from lllm.session_store import session_database_uri
from lllm.web import ComposedAppLoader, _ExpandCallbackTokensOnOutput, build_web_app


class WebRequestReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_sse_replay_returns_the_body_then_the_disconnect(self):
        seen = {}

        async def app(scope, receive, send):
            del scope
            message = await receive()
            seen["body"] = message["body"]
            while True:
                follow_up = await receive()
                if follow_up["type"] == "http.disconnect":
                    break
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {
                    "type": "http.response.body",
                    "body": b'data: {"text":"ok"}\n\n',
                    "more_body": False,
                }
            )

        queued = [
            {
                "type": "http.request",
                "body": b'{"session_id":"session-1"}',
                "more_body": False,
            },
            {"type": "http.disconnect"},
        ]

        async def receive():
            return queued.pop(0)

        sent = []

        async def send(message):
            sent.append(message)

        await asyncio.wait_for(
            _ExpandCallbackTokensOnOutput(app)(
                {"type": "http", "path": "/run_sse"},
                receive,
                send,
            ),
            timeout=2,
        )
        self.assertEqual(seen["body"], b'{"session_id":"session-1"}')
        self.assertEqual(sent[0]["status"], 200)
        self.assertIn(b"ok", sent[1]["body"])


class WebAppLoaderTests(unittest.TestCase):
    def test_named_apps_use_prefixed_lllm_keys(self):
        apps = named_apps()
        self.assertEqual(
            set(apps),
            {
                "lllm_browser_agent",
                "lllm_files_agent",
                "lllm_default_agent",
            },
        )
        self.assertIs(apps["lllm_default_agent"], app)
        self.assertEqual(app.name, "lllm_default_agent")
        self.assertEqual(apps["lllm_browser_agent"].name, "lllm_browser_agent")
        self.assertEqual(apps["lllm_browser_agent"].root_agent.mode, "chat")
        self.assertEqual(apps["lllm_files_agent"].name, "lllm_files_agent")
        self.assertEqual(app_for_agent("lllm").name, "lllm_default_agent")
        self.assertEqual(app_for_agent("browser_agent").name, "lllm_browser_agent")
        self.assertEqual(prefixed_app_name("browser_agent"), "lllm_browser_agent")

    def test_the_loader_lists_and_loads_those_apps(self):
        loader = ComposedAppLoader()
        self.assertEqual(
            loader.list_agents(),
            [
                "lllm_browser_agent",
                "lllm_default_agent",
                "lllm_files_agent",
            ],
        )
        self.assertEqual(
            loader.load_agent("lllm_default_agent").name, "lllm_default_agent"
        )
        self.assertEqual(loader.load_agent("lllm").name, "lllm_default_agent")
        self.assertEqual(
            loader.load_agent("browser_agent").name, "lllm_browser_agent"
        )
        self.assertEqual(
            loader.load_agent("lllm_browser_agent").name, "lllm_browser_agent"
        )
        details = {item["name"]: item for item in loader.list_agents_detailed()}
        self.assertEqual(
            details["lllm_browser_agent"]["display_name"], "lllm_browser_agent"
        )
        with self.assertRaises(ValueError):
            loader.load_agent("missing")

    def test_list_apps_endpoint_returns_the_cli_agent_names(self):
        # The stock UI calls /list-apps without detailed=true.
        with TestClient(
            build_web_app(), base_url="http://127.0.0.1:8000"
        ) as client:
            response = client.get("/list-apps")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                "lllm_browser_agent",
                "lllm_default_agent",
                "lllm_files_agent",
            ],
        )
        self.assertNotIn("lllm", response.json())
        self.assertNotIn("browser_agent", response.json())

    def test_the_session_uri_points_at_the_sqlite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / ".adk" / "session.db"
            uri = session_database_uri(database)
            self.assertTrue(uri.startswith("sqlite:///"))
            self.assertTrue(uri.endswith(str(database.resolve())))
            self.assertTrue(database.parent.is_dir())

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lllm.agent import app, app_for_agent, named_apps, prefixed_app_name
from lllm.session_store import session_database_uri
from lllm.web import ComposedAppLoader, build_web_app


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

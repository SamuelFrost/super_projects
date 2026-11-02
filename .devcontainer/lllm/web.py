"""ADK web UI for the same named apps and session database as the CLI."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils.base_agent_loader import BaseAgentLoader

from lllm.agent import named_apps, prefixed_app_name
from lllm.session_store import session_database_uri
from lllm.session_transcript import install_session_transcript_writer
from lllm.tools.callback_tokens import expand_callback_token_output_body

_SESSION_ID_IN_PATH = re.compile(r"/sessions/([^/]+)")

install_session_transcript_writer()

_PACKAGE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000


class ComposedAppLoader(BaseAgentLoader):
    """Serve the prefixed `lllm_*` app names the CLI uses."""

    def __init__(self) -> None:
        self._apps = named_apps()

    def load_agent(self, agent_name: str):
        canonical_name = prefixed_app_name(agent_name)
        try:
            return self._apps[canonical_name]
        except KeyError as error:
            known = ", ".join(self.list_agents())
            raise ValueError(
                f"unknown app {agent_name!r}; choose from {known}"
            ) from error

    def list_agents(self) -> list[str]:
        return sorted(self._apps)

    def list_agents_detailed(self) -> list[dict]:
        details = []
        for name in self.list_agents():
            loaded = self._apps[name]
            details.append(
                {
                    "name": name,
                    "display_name": name,
                    "description": loaded.root_agent.description,
                    "type": type(loaded.root_agent).__name__,
                }
            )
        return details


class _ExpandCallbackTokensOnOutput:
    """Show stored text in the web UI. The session row keeps the token."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        session_id = None
        path_match = _SESSION_ID_IN_PATH.search(path)
        if path_match:
            session_id = path_match.group(1)
        if path.rstrip("/").endswith("/run_sse"):
            body = await _read_http_body(receive)
            try:
                session_id = json.loads(body.decode("utf-8")).get("session_id") or session_id
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
            # StreamingResponse waits on receive() for http.disconnect. A replay
            # that keeps returning http.request never lets that wait finish, so
            # the event loop spins and the UI never gets a byte of the stream.
            receive = _replay_http_body(body, receive)

        if not session_id:
            await self.app(scope, receive, send)
            return

        content_type = ""

        async def send_expanded(message):
            nonlocal content_type
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                for name, value in headers:
                    if name.lower() == b"content-type":
                        content_type = value.decode("latin1")
                if any(name.lower() == b"content-length" for name, _value in headers):
                    headers = [
                        (name, value)
                        for name, value in headers
                        if name.lower() != b"content-length"
                    ]
                    message = {**message, "headers": headers}
            elif message["type"] == "http.response.body" and message.get("body"):
                message = {
                    **message,
                    "body": expand_callback_token_output_body(
                        message["body"], session_id, content_type
                    ),
                }
            await send(message)

        await self.app(scope, receive, send_expanded)


async def _read_http_body(receive) -> bytes:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return bytes(body)
        if message["type"] != "http.request":
            continue
        body.extend(message.get("body") or b"")
        if not message.get("more_body", False):
            return bytes(body)


def _replay_http_body(body: bytes, original_receive):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await original_receive()

    return receive


def build_web_app(*, host: str = DEFAULT_WEB_HOST, port: int = DEFAULT_WEB_PORT):
    """FastAPI app that lists the CLI apps and reads the shared session.db."""
    app = get_fast_api_app(
        agents_dir=str(_PACKAGE_DIRECTORY),
        agent_loader=ComposedAppLoader(),
        session_service_uri=session_database_uri(),
        web=True,
        host=host,
        bind_host=host,
        port=port,
    )
    return _ExpandCallbackTokensOnOutput(app)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lllm web",
        description=(
            "Start the ADK web UI for lllm_default_agent, lllm_browser_agent, and lllm_files_agent. "
            "Sessions are the same rows the CLI stores in .adk/session.db."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_WEB_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_WEB_PORT)
    return parser


def main() -> None:
    parsed_args = _build_argument_parser().parse_args()
    import uvicorn

    uvicorn.run(
        build_web_app(host=parsed_args.host, port=parsed_args.port),
        host=parsed_args.host,
        port=parsed_args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

"""ADK web UI for the same named apps and session database as the CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils.base_agent_loader import BaseAgentLoader

from lllm.agent import named_apps, prefixed_app_name
from lllm.session_store import session_database_uri

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


def build_web_app(*, host: str = DEFAULT_WEB_HOST, port: int = DEFAULT_WEB_PORT):
    """FastAPI app that lists the CLI apps and reads the shared session.db."""
    return get_fast_api_app(
        agents_dir=str(_PACKAGE_DIRECTORY),
        agent_loader=ComposedAppLoader(),
        session_service_uri=session_database_uri(),
        web=True,
        host=host,
        bind_host=host,
        port=port,
    )


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

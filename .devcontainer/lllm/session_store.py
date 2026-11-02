"""Locate the shared ADK session database.

`lllm` stores sessions in `.devcontainer/lllm/.adk/session.db`. Rows are
keyed by the app name and the user id `user`. ADK's session service owns the
events.
"""

from pathlib import Path

_PACKAGE_DIRECTORY = Path(__file__).resolve().parent
SESSION_USER_ID = "user"


class UnknownSessionError(LookupError):
    """No session exists for this id, user, and app in the session database."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(session_id)


def default_session_database() -> Path:
    """The SQLite file the CLI stores sessions in."""
    return _PACKAGE_DIRECTORY / ".adk" / "session.db"


def session_database_uri(session_db: Path | None = None) -> str:
    """ADK `sqlite://` URI for `SqliteSessionService`."""
    database = (session_db or default_session_database()).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database}"

"""Locate the shared ADK session database and the CLI output directory.

`lllm` and `lllm web` both use `.devcontainer/lllm/.adk/session.db`. Rows are
keyed by the prefixed app name (`lllm_default_agent`, `lllm_browser_agent`,
`lllm_files_agent`) and the user id `user`. ADK's session service owns the
events.
"""

import os
from pathlib import Path

_PACKAGE_DIRECTORY = Path(__file__).resolve().parent
SESSION_USER_ID = "user"


class UnknownSessionError(LookupError):
    """No session exists for this id, user, and app in the session database."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(session_id)


def default_log_directory() -> Path:
    """Directory for `session_transcripts/<app>/<session id>/transcript.txt`.

    The journal is gitignored because it lives under `.local_only`.
    `session.db` stays in `.adk`.
    """
    return _PACKAGE_DIRECTORY / ".local_only" / "local_llm_journal"


def default_session_database() -> Path:
    """The SQLite file the CLI and `lllm web` share."""
    return _PACKAGE_DIRECTORY / ".adk" / "session.db"


def session_database_uri(session_db: Path | None = None) -> str:
    """ADK `sqlite://` URI for `SqliteSessionService`."""
    database = (session_db or default_session_database()).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database}"


def resolve_log_directory(explicit_log_dir: str | None) -> Path:
    """`--log-dir` wins, then `LLLM_LOG_DIR`, then the local journal."""
    if explicit_log_dir:
        return Path(explicit_log_dir)
    from_environment = os.environ.get("LLLM_LOG_DIR")
    if from_environment:
        return Path(from_environment)
    return default_log_directory()

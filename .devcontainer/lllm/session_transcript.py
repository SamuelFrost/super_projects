"""Write one transcript for a session from the events stored in session.db.

CLI and `lllm web` both append to that database. Each persisted event rewrites
`.local_only/local_llm_journal/session_transcripts/<app>/<session id>/transcript.txt`,
so a turn from either side is in the same file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google.adk.sessions.sqlite_session_service import SqliteSessionService

from lllm.session_store import default_session_database, resolve_log_directory
from lllm.tools.callback_tokens import expand_callback_tokens_for_session

_TRANSCRIPT_DIRECTORY_ATTRIBUTE = "_lllm_transcript_dir"
_append_event_installed = False


def session_transcript_path(log_dir: Path, app_name: str, session_id: str) -> Path:
    """The combined transcript for one app session."""
    return log_dir / "session_transcripts" / app_name / session_id / "transcript.txt"


def render_session_transcript(session) -> str:
    """Every stored user, model, and tool message, in session order."""
    blocks = []
    for event in session.events or []:
        block = _render_event(event)
        if block:
            blocks.append(block)
    if not blocks:
        return ""
    rendered = "\n\n".join(blocks) + "\n"
    return expand_callback_tokens_for_session(rendered, getattr(session, "id", "") or "")


def write_session_transcript(log_dir: Path, session) -> Path:
    """Replace the session transcript with the events currently stored."""
    path = session_transcript_path(log_dir, session.app_name, session.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".txt.tmp")
    temporary.write_text(render_session_transcript(session), encoding="utf-8")
    temporary.replace(path)
    return path


def install_session_transcript_writer() -> None:
    """Record a full transcript whenever the shared SQLite service stores an event."""
    global _append_event_installed
    if _append_event_installed:
        return
    _append_event_installed = True
    original_append_event = SqliteSessionService.append_event

    async def append_event_and_write_transcript(self, session, event):
        stored_event = await original_append_event(self, session, event)
        if getattr(event, "partial", False):
            return stored_event
        log_dir = _transcript_directory_for_service(self)
        if log_dir is None:
            return stored_event
        try:
            stored_session = await self.get_session(
                app_name=session.app_name,
                user_id=session.user_id,
                session_id=session.id,
            )
            if stored_session is not None:
                write_session_transcript(log_dir, stored_session)
        except Exception as error:
            print(f"lllm: could not write the session transcript: {error}", file=sys.stderr)
        return stored_event

    SqliteSessionService.append_event = append_event_and_write_transcript


def _transcript_directory_for_service(session_service) -> Path | None:
    explicit_directory = getattr(session_service, _TRANSCRIPT_DIRECTORY_ATTRIBUTE, None)
    if explicit_directory is not None:
        return Path(explicit_directory)
    database_path = getattr(session_service, "_db_path", None)
    if database_path is None:
        return None
    if Path(database_path).resolve() != default_session_database().resolve():
        return None
    return resolve_log_directory(None)


def _render_event(event) -> str:
    content = event.content
    if content is None or not content.parts:
        return ""
    author = event.author or "unknown"
    sections = []
    for part in content.parts:
        function_call = part.function_call
        if function_call is not None and function_call.name:
            rendered_arguments = ""
            if function_call.args:
                rendered_arguments = " " + json.dumps(
                    function_call.args, ensure_ascii=False, default=str
                )
            sections.append(f"[{author} tool call]\n{function_call.name}{rendered_arguments}")
            continue
        function_response = part.function_response
        if function_response is not None:
            tool_name = function_response.name or "tool"
            payload = function_response.response
            if not isinstance(payload, str):
                payload = json.dumps(payload, ensure_ascii=False, default=str)
            sections.append(f"[{author} tool result]\n{tool_name}\n{payload}")
            continue
        if part.text and part.thought:
            sections.append(f"[{author} thinking]\n{part.text}")
            continue
        if part.text:
            sections.append(f"[{author}]\n{part.text}")
    return "\n\n".join(sections)

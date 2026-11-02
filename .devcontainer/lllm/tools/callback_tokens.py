"""Store large or fragile text behind a short token for one lllm session.

Local models lose context quickly and often mangle long URLs or large text
blocks when copying them across tool calls and sub-agent reports. This module
replaces those strings with compact `[encoded_callback_token <number>_<timestamp>]`
placeholders. The text is stored in `session.db`, keyed by the lllm session id
and the token id, so a lookup cannot read another session's text.

- Creation: `list_pages` automatically tokenizes long URLs, and agents can call
  `store_callback_token` to save reusable text blocks (up to 10 MB per session).
- Inspection: Agents can list tokens (`list_stored_callback_tokens`) or inspect
  their metadata, character count, and 20-character bookends (`preview_callback_token`)
  without pulling the full text back into context.
- Automatic recall: `prepare_tool_arguments` expands tokens inside outgoing tool
  arguments before the tool runs, and output paths expand tokens when text is
  shown. The token text itself is unchanged.
"""

import contextvars
import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

from lllm.session_store import default_session_database

_CALLBACK_TOKEN_OPEN = "[encoded_callback_token "
# Text shorter than 20 characters stays as written.
_CALLBACK_TOKEN_PREVIEW_LENGTH = 20
_CALLBACK_TOKEN_MINIMUM_TEXT_LENGTH = _CALLBACK_TOKEN_PREVIEW_LENGTH
# The id is the only field, so a long quote cannot be read as a token.
_CALLBACK_TOKEN_IN_TEXT = re.compile(r"\[encoded_callback_token (\d+_\d+)\]")
_CALLBACK_TOKEN_ID = re.compile(r"\d+_\d+")
_CALLBACK_TOKEN_TOOL_NAMES = frozenset(
    {
        "recall_callback_token",
        "preview_callback_token",
        "store_callback_token",
        "list_stored_callback_tokens",
    }
)
_next_callback_token_number: contextvars.ContextVar[list[int] | None] = (
    contextvars.ContextVar("lllm_next_callback_token_number", default=None)
)
# Child tasks must mutate this dict. Replacing the context variable
# would hide the stored text from the rest of the turn.
_callback_tokens_for_turn: contextvars.ContextVar[dict | None] = (
    contextvars.ContextVar("lllm_callback_tokens_for_turn", default=None)
)
_active_callback_session_id: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("lllm_active_callback_session_id", default=None)
)
_callback_token_database: contextvars.ContextVar[Path | None] = (
    contextvars.ContextVar("lllm_callback_token_database", default=None)
)
_CALLBACK_TOKEN_CHARACTER_LIMIT = 10 * 1024 * 1024
_stored_callback_character_count: contextvars.ContextVar[int] = (
    contextvars.ContextVar("lllm_stored_callback_character_count", default=0)
)
_EPHEMERAL_SESSION_PREFIX = "ephemeral:"
_callback_token_database_lock = threading.Lock()


def begin_callback_token_tracking() -> None:
    """Start a turn-local bucket until a real lllm session is bound."""
    session_id = f"{_EPHEMERAL_SESSION_PREFIX}{uuid.uuid4()}"
    _active_callback_session_id.set(session_id)
    _callback_tokens_for_turn.set({})
    _next_callback_token_number.set([1])
    _stored_callback_character_count.set(0)


def bind_callback_tokens_to_session(session_id: str, database: Path | None = None) -> None:
    """Look up tokens for this lllm session. The same bucket is shared with child tasks."""
    if not session_id or session_id.startswith(_EPHEMERAL_SESSION_PREFIX):
        return
    if database is not None:
        _callback_token_database.set(database)
    if (
        _active_callback_session_id.get() == session_id
        and isinstance(_callback_tokens_for_turn.get(), dict)
    ):
        return
    bucket = _load_callback_tokens(session_id)
    _active_callback_session_id.set(session_id)
    _callback_tokens_for_turn.set(bucket)
    _stored_callback_character_count.set(_character_count(bucket))


def use_callback_token_database(database: Path) -> None:
    """Store callback tokens in this session.db instead of the shared default."""
    _callback_token_database.set(database)


def _session_id_from_tool_context(tool_context) -> str | None:
    session = getattr(tool_context, "session", None)
    session_id = getattr(session, "id", None)
    if isinstance(session_id, str) and session_id:
        return session_id
    active_session_id = _active_callback_session_id.get()
    if isinstance(active_session_id, str) and active_session_id:
        return active_session_id
    return None


def _use_session(session_id: str | None) -> str:
    if session_id:
        if not session_id.startswith(_EPHEMERAL_SESSION_PREFIX):
            bind_callback_tokens_to_session(session_id)
        return session_id
    active_session_id = _active_callback_session_id.get()
    if isinstance(active_session_id, str) and active_session_id:
        return active_session_id
    begin_callback_token_tracking()
    return _active_callback_session_id.get() or ""


def _turn_tokens() -> dict:
    session_id = _use_session(None)
    if (
        _active_callback_session_id.get() == session_id
        and isinstance(_callback_tokens_for_turn.get(), dict)
    ):
        return _callback_tokens_for_turn.get()
    bind_callback_tokens_to_session(session_id)
    tokens_by_id = _callback_tokens_for_turn.get()
    if not isinstance(tokens_by_id, dict):
        tokens_by_id = {}
        _callback_tokens_for_turn.set(tokens_by_id)
    return tokens_by_id


def _character_count(tokens_by_id: dict) -> int:
    return sum(len(_callback_token_text(stored) or "") for stored in tokens_by_id.values())


def _callback_token_database_path() -> Path:
    database = _callback_token_database.get()
    if database is None:
        return default_session_database()
    return database


def _persistent_session(session_id: str | None) -> bool:
    return bool(session_id) and not session_id.startswith(_EPHEMERAL_SESSION_PREFIX)


def _connect_callback_token_database() -> sqlite3.Connection:
    database = _callback_token_database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=5)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS lllm_callback_tokens (
            session_id TEXT NOT NULL,
            token_id TEXT NOT NULL,
            text TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (session_id, token_id)
        )
        """
    )
    return connection


def _load_callback_tokens(session_id: str) -> dict:
    if not _persistent_session(session_id):
        return {}
    with _callback_token_database_lock:
        connection = _connect_callback_token_database()
        try:
            rows = connection.execute(
                """
                SELECT token_id, text, note, description
                FROM lllm_callback_tokens
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchall()
        finally:
            connection.close()
    return {
        token_id: {"text": text, "note": note, "description": description}
        for token_id, text, note, description in rows
    }


def _save_callback_token(session_id: str, token_id: str, stored: dict) -> None:
    if not _persistent_session(session_id):
        return
    with _callback_token_database_lock:
        connection = _connect_callback_token_database()
        try:
            connection.execute(
                """
                INSERT INTO lllm_callback_tokens (
                    session_id, token_id, text, note, description
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, token_id) DO UPDATE SET
                    note = excluded.note,
                    description = excluded.description
                """,
                (
                    session_id,
                    token_id,
                    stored.get("text") or "",
                    stored.get("note") or "",
                    stored.get("description") or "",
                ),
            )
            connection.commit()
        finally:
            connection.close()


def _callback_token_preview(stored_text: str) -> tuple[str, str]:
    """The first 20 characters and the last 20. Line breaks stay on one line."""
    preview = stored_text.replace("\r", " ").replace("\n", " ")
    return preview[:_CALLBACK_TOKEN_PREVIEW_LENGTH], preview[-_CALLBACK_TOKEN_PREVIEW_LENGTH:]


def _format_callback_token(token_id: str) -> str:
    return f"[encoded_callback_token {token_id}]"


def _new_callback_token_id() -> str:
    """A turn counter and the current time in milliseconds."""
    numbers = _next_callback_token_number.get()
    if not isinstance(numbers, list) or not numbers:
        numbers = [1]
        _next_callback_token_number.set(numbers)
    number = numbers[0]
    numbers[0] = number + 1
    return f"{number}_{int(time.time() * 1000)}"


def _callback_token_id_for_text(stored_text: str, tokens_by_id: dict) -> str | None:
    for token_id, stored in tokens_by_id.items():
        if _callback_token_text(stored) == stored_text:
            return token_id
    return None


def _callback_token_text(stored) -> str | None:
    if isinstance(stored, dict) and isinstance(stored.get("text"), str):
        return stored["text"]
    return None


def _callback_token_field(stored, field: str) -> str:
    if isinstance(stored, dict) and isinstance(stored.get(field), str):
        return stored[field]
    return ""


def _store_callback_token(
    stored_text: str,
    note: str = "",
    description: str = "",
) -> str | None:
    """Store text and return its token. Text under 20 characters stays put."""
    text_length = len(stored_text)
    if text_length < _CALLBACK_TOKEN_MINIMUM_TEXT_LENGTH:
        return None
    if not isinstance(note, str):
        note = ""
    if not isinstance(description, str):
        description = ""
    tokens_by_id = _turn_tokens()
    session_id = _active_callback_session_id.get() or ""
    token_id = _callback_token_id_for_text(stored_text, tokens_by_id)
    if token_id is None:
        character_count = _stored_callback_character_count.get()
        if character_count + text_length > _CALLBACK_TOKEN_CHARACTER_LIMIT:
            return None
        _stored_callback_character_count.set(character_count + text_length)
        token_id = _new_callback_token_id()
        stored = {
            "text": stored_text,
            "note": note,
            "description": description,
        }
        tokens_by_id[token_id] = stored
        _save_callback_token(session_id, token_id, stored)
        return _format_callback_token(token_id)
    stored = tokens_by_id[token_id]
    changed = False
    if note and not stored.get("note"):
        stored["note"] = note
        changed = True
    if description and not stored.get("description"):
        stored["description"] = description
        changed = True
    if changed:
        _save_callback_token(session_id, token_id, stored)
    return _format_callback_token(token_id)


def store_callback_token(
    text: str,
    note: str = "",
    description: str = "",
    *,
    tool_context: ToolContext | None = None,
) -> dict:
    """Store text as a callback token.

    Use this when a large block of text will be passed around or frequently reused.
    Pass that token instead of repeating the text. Text shorter than 20 characters
    is left as written. note and description are shown by preview_callback_token.
    """
    _use_session(_session_id_from_tool_context(tool_context))
    token = _store_callback_token(
        text,
        note if isinstance(note, str) else "",
        description if isinstance(description, str) else "",
    )
    if token is None and len(text) >= _CALLBACK_TOKEN_MINIMUM_TEXT_LENGTH:
        return {"stored": False, "reason": "callback token storage reached its character limit"}
    if token is None:
        return {"stored": False, "text": text}
    return {"stored": True, "callback_token": token}


def _text_with_callback_tokens_expanded(text: str, session_id: str | None = None) -> str:
    resolved_session_id = _use_session(session_id)

    def expand(token_match):
        stored_text = _stored_callback_text(token_match.group(1), resolved_session_id)
        if not isinstance(stored_text, str):
            return token_match.group(0)
        return stored_text

    return _CALLBACK_TOKEN_IN_TEXT.sub(expand, text)


def expand_callback_tokens_for_session(text: str, session_id: str) -> str:
    """Replace tokens in displayed text using this lllm session's stored values."""
    if not text or not session_id:
        return text
    return _text_with_callback_tokens_expanded(text, session_id)


def expand_callback_token_output_body(body: bytes, session_id: str, content_type: str = "") -> bytes:
    """Expand tokens in a web response body. Stored events stay tokenized."""
    if not body or not session_id:
        return body
    text = body.decode("utf-8")
    if "text/event-stream" in content_type or text.lstrip().startswith("data:"):
        return _expand_server_sent_events(text, session_id).encode("utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return expand_callback_tokens_for_session(text, session_id).encode("utf-8")
    return json.dumps(
        expand_callback_tokens_in_output(value, session_id),
        ensure_ascii=False,
    ).encode("utf-8")


def _expand_server_sent_events(text: str, session_id: str) -> str:
    expanded_lines = []
    for line in text.splitlines(keepends=True):
        payload_line = line[:-1] if line.endswith("\n") else line
        newline = "\n" if line.endswith("\n") else ""
        if not payload_line.startswith("data:"):
            expanded_lines.append(line)
            continue
        payload = payload_line[5:].strip()
        if not payload or payload == "[DONE]":
            expanded_lines.append(line)
            continue
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            expanded_lines.append(line)
            continue
        expanded = json.dumps(
            expand_callback_tokens_in_output(value, session_id),
            ensure_ascii=False,
        )
        expanded_lines.append(f"data: {expanded}{newline}")
    return "".join(expanded_lines)


def expand_callback_tokens_in_output(value, session_id: str):
    """Expand tokens in a JSON-like output value without changing stored events."""
    if isinstance(value, str):
        return expand_callback_tokens_for_session(value, session_id)
    if isinstance(value, list):
        return [expand_callback_tokens_in_output(item, session_id) for item in value]
    if isinstance(value, dict):
        return {
            key: expand_callback_tokens_in_output(item, session_id)
            for key, item in value.items()
        }
    return value


def _expand_callback_tokens_in_value(value):
    if isinstance(value, str):
        return _text_with_callback_tokens_expanded(value)
    if isinstance(value, list):
        return [_expand_callback_tokens_in_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _expand_callback_tokens_in_value(item) for key, item in value.items()
        }
    return value


def _expand_callback_tokens(tool_args) -> None:
    if not isinstance(tool_args, dict):
        return
    for key, value in list(tool_args.items()):
        tool_args[key] = _expand_callback_tokens_in_value(value)


def _unfinished_callback_token_suffix(text: str) -> tuple[str, str]:
    """Split off a trailing `[encoded_callback_token ...` that hasn't closed yet.

    SSE streaming can split a token across two text chunks. Holding the unfinished
    suffix until the closing `]` arrives prevents partial tokens from leaking to
    stdout unexpanded.
    """
    bracket_at = text.rfind("[")
    if bracket_at == -1:
        return text, ""
    tail = text[bracket_at:]
    token_is_unfinished = "]" not in tail and (
        _CALLBACK_TOKEN_OPEN.startswith(tail) or tail.startswith(_CALLBACK_TOKEN_OPEN)
    )
    if token_is_unfinished:
        return text[:bracket_at], tail
    return text, ""


def expand_visible_callback_tokens(text: str, *, flush: bool) -> tuple[str, str]:
    """Replace callback tokens in an answer with the stored text for this session."""
    session_id = _active_callback_session_id.get()
    if not session_id:
        return text, ""
    held_token = ""
    if not flush:
        text, held_token = _unfinished_callback_token_suffix(text)
    return _text_with_callback_tokens_expanded(text, session_id), held_token


def _callback_token_id_from_text(text: str) -> str:
    """Extract `<number>_<timestamp>` from a raw ID, full token, or JSON string.

    Models frequently pass the entire `[encoded_callback_token 1_1700000000000]`
    string, attach a trailing label after a colon, or wrap the argument in JSON
    when calling preview or recall tools.
    """
    token_match = _CALLBACK_TOKEN_IN_TEXT.search(text)
    if token_match:
        return token_match.group(1)
    stripped = text.strip().strip("[]")
    for prefix in ("encoded_callback_token ", "encoded_callback_token:"):
        stripped = stripped.removeprefix(prefix)
    id_value = _CALLBACK_TOKEN_ID.match(stripped)
    if id_value and (
        id_value.end() == len(stripped) or stripped[id_value.end()] in " :]"
    ):
        return id_value.group(0)
    if stripped[:1] in "{[":
        try:
            return _callback_token_id_from_argument(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return stripped


def _callback_token_id_from_argument(argument) -> str:
    """Accept <number>_<timestamp>, or the whole [encoded_callback_token ...] token."""
    if isinstance(argument, list) and len(argument) == 1:
        return _callback_token_id_from_argument(argument[0])
    if isinstance(argument, dict):
        for key in ("id", "encoded_callback_token"):
            if key in argument:
                return _callback_token_id_from_argument(argument[key])
        return str(argument)
    if isinstance(argument, bool) or argument is None:
        return str(argument)
    if isinstance(argument, int):
        return str(argument)
    if isinstance(argument, str):
        return _callback_token_id_from_text(argument)
    return str(argument)


def _adopt_callback_token_arguments(tool_args) -> None:
    """Normalize alternative argument names into `id` for callback-token tools.

    Small models sometimes call `preview_callback_token` or `recall_callback_token`
    with `{"encoded_callback_token": "..."}` or `{"callback_token": "..."}`
    instead of `{"id": "..."}`.
    """
    if not isinstance(tool_args, dict) or "id" in tool_args:
        return
    for key in ("encoded_callback_token", "recall_callback_token", "callback_token"):
        if key in tool_args:
            nested = tool_args.pop(key)
            break
    else:
        return
    if isinstance(nested, dict) and "id" in nested:
        tool_args["id"] = nested["id"]
        return
    tool_args["id"] = nested


def prepare_tool_arguments(tool_name: str | None, tool_args) -> None:
    """Recall tokens inside a tool call before it runs.

    The callback-token tools keep the token. Their arguments are only normalized
    into id. Every other tool receives the stored text.
    """
    if tool_name in _CALLBACK_TOKEN_TOOL_NAMES:
        _adopt_callback_token_arguments(tool_args)
        return
    _expand_callback_tokens(tool_args)


def list_stored_callback_tokens(*, tool_context: ToolContext | None = None) -> dict:
    """List the id and description of each callback token stored for this session."""
    _use_session(_session_id_from_tool_context(tool_context))
    listed = []
    tokens_by_id = _turn_tokens()
    if not isinstance(tokens_by_id, dict):
        return {"stored_callback_tokens": listed}
    for token_id, stored in tokens_by_id.items():
        if _callback_token_text(stored) is None:
            continue
        listed.append(
            {"id": token_id, "description": _callback_token_field(stored, "description")}
        )
    return {"stored_callback_tokens": listed}


def _stored_callback_entry(token_id: str, session_id: str | None = None):
    _use_session(session_id)
    tokens_by_id = _turn_tokens()
    if not isinstance(tokens_by_id, dict):
        return None
    stored = tokens_by_id.get(token_id)
    if _callback_token_text(stored) is None:
        return None
    return stored


def _stored_callback_text(token_id: str, session_id: str | None = None) -> str | None:
    return _callback_token_text(_stored_callback_entry(token_id, session_id))


def preview_callback_token(
    id: str | int | dict | list | None = None,
    *,
    tool_context: ToolContext | None = None,
) -> dict:
    """Return the first 20 characters, last 20 characters, and character count stored for a token.

    Pass id as <number>_<timestamp>, or the whole
    [encoded_callback_token <number>_<timestamp>] token.
    The full text is recalled when the token is passed through, so use this
    only to recognize which token is which. A note and description stored with
    the token are included. character_count is the number of characters in the
    stored text. The lookup uses the current lllm session together with the token.
    """
    session_id = _session_id_from_tool_context(tool_context)
    token_id = _callback_token_id_from_argument(id)
    stored = _stored_callback_entry(token_id, session_id)
    stored_text = _callback_token_text(stored)
    if stored_text is None:
        return {"id": token_id, "missing": True}
    first_20, last_20 = _callback_token_preview(stored_text)
    return {
        "id": token_id,
        "first_20_characters": first_20,
        "last_20_characters": last_20,
        "character_count": len(stored_text),
        "note": _callback_token_field(stored, "note"),
        "description": _callback_token_field(stored, "description"),
    }


def recall_callback_token(
    id: str | int | dict | list | None = None,
    *,
    tool_context: ToolContext | None = None,
) -> dict:
    """This tool reads the large text stored for a callback token.
    It is automatically called when reporting, so agents should not call this.
    Instead, if you need to know the contents, call the preview_callback_token tool and reference the token unchanged.
    Trust that the token will be recalled when needed for tool calls or reports. So prefer checking the preview unless you must see the full contents.

    Pass the whole token object:
    [encoded_callback_token <number>_<timestamp>] token.
    The id selects the stored text for the current lllm session.
    """
    session_id = _session_id_from_tool_context(tool_context)
    token_id = _callback_token_id_from_argument(id)
    stored_text = _stored_callback_text(token_id, session_id)
    if stored_text is None:
        return {"id": token_id, "missing": True}
    return {"id": token_id, "text": stored_text}

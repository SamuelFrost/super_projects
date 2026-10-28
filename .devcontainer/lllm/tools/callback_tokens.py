"""Store large or fragile text behind a short token for the duration of a turn.

Local models lose context quickly and often mangle long URLs or large text
blocks when copying them across tool calls and sub-agent reports. This module
replaces those strings with compact `[encoded_callback_token <number>_<timestamp>]`
placeholders stored in a per-turn map:

- Creation: `list_pages` automatically tokenizes long URLs, and agents can call
  `store_callback_token` to save reusable text blocks (up to 10 MB per turn).
- Inspection: Agents can list tokens (`list_stored_callback_tokens`) or inspect
  their metadata, character count, and 20-character bookends (`preview_callback_token`)
  without pulling the full text back into context.
- Automatic recall: `prepare_tool_arguments` expands tokens inside outgoing tool
  arguments before the tool runs, and `expand_visible_callback_tokens` expands
  tokens in the root agent's final answer as it streams to the user.
"""

import contextvars
import json
import re
import time

from google.adk.tools.tool_context import ToolContext

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
_CALLBACK_TOKEN_CHARACTER_LIMIT = 10 * 1024 * 1024
_stored_callback_character_count: contextvars.ContextVar[int] = (
    contextvars.ContextVar("lllm_stored_callback_character_count", default=0)
)


def begin_callback_token_tracking() -> None:
    _callback_tokens_for_turn.set({})
    _next_callback_token_number.set([1])
    _stored_callback_character_count.set(0)


def _turn_tokens() -> dict:
    tokens_by_id = _callback_tokens_for_turn.get()
    if not isinstance(tokens_by_id, dict):
        tokens_by_id = {}
        _callback_tokens_for_turn.set(tokens_by_id)
    return tokens_by_id


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
    token_id = _callback_token_id_for_text(stored_text, tokens_by_id)
    if token_id is None:
        character_count = _stored_callback_character_count.get()
        if character_count + text_length > _CALLBACK_TOKEN_CHARACTER_LIMIT:
            return None
        _stored_callback_character_count.set(character_count + text_length)
        token_id = _new_callback_token_id()
        tokens_by_id[token_id] = {
            "text": stored_text,
            "note": note,
            "description": description,
        }
        return _format_callback_token(token_id)
    stored = tokens_by_id[token_id]
    if note and not stored.get("note"):
        stored["note"] = note
    if description and not stored.get("description"):
        stored["description"] = description
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
    del tool_context
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


def _text_with_callback_tokens_expanded(text: str) -> str:
    def expand(token_match):
        stored_text = _stored_callback_text(token_match.group(1))
        if not isinstance(stored_text, str):
            return token_match.group(0)
        return stored_text

    return _CALLBACK_TOKEN_IN_TEXT.sub(expand, text)


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
    """Replace callback tokens in an answer with the stored text."""
    tokens_by_id = _callback_tokens_for_turn.get()
    if not isinstance(tokens_by_id, dict) or not tokens_by_id:
        return text, ""
    held_token = ""
    if not flush:
        text, held_token = _unfinished_callback_token_suffix(text)
    return _text_with_callback_tokens_expanded(text), held_token


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
    """List the id and description of each stored callback token."""
    del tool_context
    listed = []
    tokens_by_id = _callback_tokens_for_turn.get()
    if not isinstance(tokens_by_id, dict):
        return {"stored_callback_tokens": listed}
    for token_id, stored in tokens_by_id.items():
        if _callback_token_text(stored) is None:
            continue
        listed.append(
            {"id": token_id, "description": _callback_token_field(stored, "description")}
        )
    return {"stored_callback_tokens": listed}


def _stored_callback_entry(token_id: str):
    tokens_by_id = _callback_tokens_for_turn.get()
    if not isinstance(tokens_by_id, dict):
        return None
    stored = tokens_by_id.get(token_id)
    if _callback_token_text(stored) is None:
        return None
    return stored


def _stored_callback_text(token_id: str) -> str | None:
    return _callback_token_text(_stored_callback_entry(token_id))


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
    stored text.
    """
    del tool_context
    token_id = _callback_token_id_from_argument(id)
    stored = _stored_callback_entry(token_id)
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
    The id selects the stored text.
    """
    del tool_context
    token_id = _callback_token_id_from_argument(id)
    stored_text = _stored_callback_text(token_id)
    if stored_text is None:
        return {"id": token_id, "missing": True}
    return {"id": token_id, "text": stored_text}

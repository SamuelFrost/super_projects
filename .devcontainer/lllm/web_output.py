"""Expand displayed callback tokens across HTTP chunks and ADK text deltas."""

import json
import re

from lllm.tools.callback_tokens import (
    expand_callback_token_text_chunk,
    expand_callback_tokens_in_output,
)

_SSE_BOUNDARY = re.compile(rb"\r?\n\r?\n")
_EVENT_IDENTITY_FIELDS = ("invocationId", "invocation_id", "id", "author", "branch")


class CallbackTokenSseExpander:
    """Frame SSE before decoding UTF-8/JSON, then expand each ADK text stream.

    HTTP chunk boundaries do not delimit SSE records, and model text deltas do
    not delimit placeholders. Only incomplete records and possible placeholder
    suffixes are held; ordinary text and event metadata continue streaming.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._buffer = bytearray()
        self._held_text: dict[tuple, tuple[str, dict]] = {}

    def feed(self, body: bytes, *, final: bool) -> bytes:
        self._buffer.extend(body)
        output = bytearray()
        while boundary := _SSE_BOUNDARY.search(self._buffer):
            record = bytes(self._buffer[: boundary.end()])
            del self._buffer[: boundary.end()]
            output.extend(self._expand_record(record))
        if final:
            if self._buffer:
                output.extend(self._expand_record(bytes(self._buffer)))
                self._buffer.clear()
            output.extend(self._flush_held_text())
        return bytes(output)

    def _expand_record(self, record: bytes) -> bytes:
        try:
            # SSE uses wire newlines, not Unicode separators inside JSON text.
            lines = re.findall(r"[^\n]*(?:\n|$)", record.decode("utf-8"))
        except UnicodeDecodeError:
            return record
        data_lines = [line[5:].strip() for line in lines if line.startswith("data:")]
        if not data_lines:
            return record
        payload = "\n".join(data_lines)
        if payload == "[DONE]":
            return self._flush_held_text() + record
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            return record

        prefix = b""
        if isinstance(value, dict):
            if "error" in value:
                prefix = self._flush_held_text()
            elif not value.get("partial"):
                content = value.get("content")
                parts = content.get("parts", []) if isinstance(content, dict) else []
                if not isinstance(parts, list) or not any(
                    isinstance(part, dict) and "text" in part for part in parts
                ):
                    prefix = self._flush_held_text(self._identity(value))
        expanded = self._expand_event(value)
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        data = "data: " + json.dumps(expanded, ensure_ascii=False) + newline
        rewritten = []
        inserted = False
        for line in lines:
            if line.startswith("data:"):
                if not inserted:
                    rewritten.append(data)
                    inserted = True
            else:
                rewritten.append(line)
        rendered = "".join(rewritten)
        if not rendered.endswith(newline + newline):
            rendered += newline
        return prefix + rendered.encode("utf-8")

    def _expand_event(self, value):
        if not isinstance(value, dict):
            return expand_callback_tokens_in_output(value, self.session_id)
        identity = self._identity(value)
        partial = bool(value.get("partial"))
        content = value.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            return expand_callback_tokens_in_output(value, self.session_id)

        if not partial:
            # The final event is authoritative full content, not another delta.
            # Do not prepend a suffix already represented in that full content.
            for key in list(self._held_text):
                if key[: len(identity)] == identity:
                    del self._held_text[key]

        displayed_text = {}
        for index, part in enumerate(parts):
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                continue
            text = part.pop("text")
            key = (*identity, index, bool(part.get("thought")))
            held, _template = self._held_text.pop(key, ("", None))
            displayed_text[index], suffix = expand_callback_token_text_chunk(
                held + text, self.session_id, flush=not partial
            )
            if suffix:
                # A flush delta contains only text, never repeated tool calls,
                # state changes, or artifacts from the original event.
                template = {
                    field: value[field]
                    for field in (*_EVENT_IDENTITY_FIELDS, "timestamp")
                    if field in value
                }
                template.update(
                    partial=True,
                    content={
                        "role": content.get("role", "model"),
                        "parts": [
                            {"text": suffix, "thought": bool(part.get("thought"))}
                        ],
                    },
                )
                self._held_text[key] = (suffix, template)

        # Expand other displayed fields once. Insert the already-expanded text
        # afterwards so a literal token inside stored text is not expanded twice.
        expanded = expand_callback_tokens_in_output(value, self.session_id)
        for index, text in displayed_text.items():
            expanded["content"]["parts"][index]["text"] = text
        return expanded

    @staticmethod
    def _identity(value) -> tuple:
        return tuple(value.get(field) for field in _EVENT_IDENTITY_FIELDS)

    def _flush_held_text(self, identity: tuple | None = None) -> bytes:
        output = bytearray()
        for key in list(self._held_text):
            if identity is not None and key[: len(identity)] != identity:
                continue
            _suffix, event = self._held_text.pop(key)
            output.extend(
                ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode(
                    "utf-8"
                )
            )
        return bytes(output)

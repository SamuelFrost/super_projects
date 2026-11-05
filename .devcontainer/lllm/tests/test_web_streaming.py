"""Callback display contracts at HTTP, SSE record, and model-delta boundaries."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lllm.tools.callback_tokens import (
    begin_callback_token_tracking,
    expand_callback_token_output_body,
    expand_callback_tokens_for_session,
    store_callback_token,
    use_callback_token_database,
)
from lllm.web import _ExpandCallbackTokensOnOutput
from lllm.web_output import CallbackTokenSseExpander


def _event(text, *, partial=True, thought=False, **metadata):
    event = {
        "id": "response-1",
        "invocationId": "invocation-1",
        "author": "lllm_default_agent",
        "partial": partial,
        "content": {"role": "model", "parts": [{"text": text, "thought": thought}]},
    }
    event.update(metadata)
    return event


def _record(value, newline="\n"):
    return ("data: " + json.dumps(value, ensure_ascii=False) + newline * 2).encode(
        "utf-8"
    )


def _events(body):
    result = []
    for record in body.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].strip() for line in record.split("\n") if line.startswith("data:")
        )
        if data and data != "[DONE]":
            result.append(json.loads(data))
    return result


def _text(event):
    return "".join(
        part.get("text", "") for part in event.get("content", {}).get("parts", [])
    )


class WebStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        use_callback_token_database(Path(directory.name) / "session.db")
        begin_callback_token_tracking()
        self.session_id = "web-session"
        self.context = SimpleNamespace(session=SimpleNamespace(id=self.session_id))
        self.value = (
            'https://example.invalid/日本語?q="quoted"\nSecond line\u2028separator'
        )
        self.token = store_callback_token(self.value, tool_context=self.context)[
            "callback_token"
        ]

    async def _request(self, app, *, body=None, path="/run_sse"):
        body = body if body is not None else {"sessionId": self.session_id}
        raw = json.dumps(body).encode()
        queued = [
            {"type": "http.request", "body": raw[:5], "more_body": True},
            {"type": "http.request", "body": raw[5:], "more_body": False},
            {"type": "http.disconnect"},
        ]
        sent = []

        async def receive():
            return queued.pop(0)

        async def send(message):
            sent.append(message)

        await asyncio.wait_for(
            _ExpandCallbackTokensOnOutput(app)(
                {"type": "http", "path": path}, receive, send
            ),
            timeout=3,
        )
        return sent

    async def test_camel_and_snake_case_session_fields_expand_and_replay_exact_body(
        self,
    ):
        for field in ("sessionId", "session_id"):
            with self.subTest(field=field):
                request_body = {field: self.session_id, "streaming": True}

                async def app(scope, receive, send):
                    message = await receive()
                    self.assertEqual(json.loads(message["body"]), request_body)
                    self.assertFalse(message["more_body"])
                    self.assertEqual((await receive())["type"], "http.disconnect")
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 200,
                            "headers": [(b"content-type", b"text/event-stream")],
                        }
                    )
                    await send(
                        {
                            "type": "http.response.body",
                            "body": _record(_event(self.token, partial=False)),
                            "more_body": False,
                        }
                    )

                sent = await self._request(app, body=request_body)
                self.assertEqual(_text(_events(sent[-1]["body"])[0]), self.value)

    async def test_http_bytes_and_model_deltas_can_both_split_at_every_character(self):
        stream = CallbackTokenSseExpander(self.session_id)
        source = b": heartbeat\n\n" + _record(_event("日本語: "))
        source += b"".join(_record(_event(character)) for character in self.token)
        source += _record(_event(" after"))
        source += _record(_event("日本語: " + self.token + " after", partial=False))
        output = bytearray()
        for byte in source:
            output.extend(stream.feed(bytes([byte]), final=False))
        output.extend(stream.feed(b"", final=True))
        events = _events(output)
        partial_text = "".join(_text(e) for e in events if e.get("partial"))
        self.assertEqual(partial_text, "日本語: " + self.value + " after")
        self.assertEqual(_text(events[-1]), partial_text)
        self.assertTrue(output.startswith(b": heartbeat\n\n"))
        self.assertTrue(all(self.token not in _text(e) for e in events))

    async def test_nonstreaming_run_uses_the_request_session_and_expands_json(self):
        async def app(scope, receive, send):
            self.assertEqual(
                json.loads((await receive())["body"])["sessionId"], self.session_id
            )
            body = json.dumps([_event(self.token, partial=False)]).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body, "more_body": False})

        sent = await self._request(app, path="/run")
        self.assertEqual(_text(json.loads(sent[-1]["body"])[0]), self.value)

    async def test_ordinary_text_streams_before_end_and_only_placeholder_suffix_is_held(
        self,
    ):
        stream = CallbackTokenSseExpander(self.session_id)
        first = stream.feed(_record(_event("Ready: [encoded_")), final=False)
        self.assertEqual(_text(_events(first)[0]), "Ready: ")
        second = stream.feed(
            _record(_event(self.token[len("[encoded_") :])), final=False
        )
        self.assertEqual(_text(_events(second)[0]), self.value)
        self.assertEqual(stream.feed(b"", final=True), b"")

    async def test_final_full_content_supersedes_a_held_partial_suffix(self):
        stream = CallbackTokenSseExpander(self.session_id)
        first = stream.feed(_record(_event("Result: " + self.token[:15])), final=False)
        final = stream.feed(
            _record(_event("Result: " + self.token, partial=False)), final=True
        )
        self.assertEqual(_text(_events(first)[0]), "Result: ")
        self.assertEqual([_text(e) for e in _events(final)], ["Result: " + self.value])

    async def test_message_author_invocation_branch_and_thought_channels_do_not_mix(
        self,
    ):
        variants = [
            {"author": "files_agent"},
            {"invocationId": "other-invocation"},
            {"branch": "other-branch"},
            {"id": "other-message"},
        ]
        for metadata in variants:
            with self.subTest(metadata=metadata):
                stream = CallbackTokenSseExpander(self.session_id)
                stream.feed(_record(_event(self.token[:22])), final=False)
                other = stream.feed(
                    _record(_event(self.token[22:], **metadata)), final=False
                )
                self.assertEqual(_text(_events(other)[0]), self.token[22:])
                original = stream.feed(_record(_event(self.token[22:])), final=True)
                self.assertEqual(_text(_events(original)[0]), self.value)
        stream = CallbackTokenSseExpander(self.session_id)
        stream.feed(_record(_event(self.token[:22], thought=True)), final=False)
        answer = stream.feed(_record(_event(self.token[22:])), final=False)
        self.assertEqual(_text(_events(answer)[0]), self.token[22:])
        thought = stream.feed(
            _record(_event(self.token[22:], thought=True)), final=True
        )
        self.assertEqual(_text(_events(thought)[0]), self.value)

        stream = CallbackTokenSseExpander(self.session_id)
        event = _event(self.token[:22])
        event["content"]["parts"].append({"text": self.token[22:]})
        first = stream.feed(_record(event), final=False)
        self.assertEqual(_text(_events(first)[0]), self.token[22:])
        event["content"]["parts"] = [
            {"text": self.token[22:]},
            {"text": " separate part"},
        ]
        second = stream.feed(_record(event), final=True)
        self.assertEqual(_text(_events(second)[0]), self.value + " separate part")

    async def test_crlf_multiline_data_and_sse_metadata_are_preserved(self):
        value = _event(
            self.token,
            partial=False,
            actions={"stateDelta": {"check": 3}, "artifactDelta": {"file.txt": 1}},
        )
        payload = json.dumps(value, ensure_ascii=False, indent=2)
        source = (
            "id: wire-id\r\nevent: message\r\nretry: 500\r\n"
            + "".join("data: " + line + "\r\n" for line in payload.split("\n"))
            + "\r\n"
        ).encode()
        stream = CallbackTokenSseExpander(self.session_id)
        output = b"".join(
            stream.feed(source[index : index + 1], final=False)
            for index in range(len(source))
        )
        output += stream.feed(b"", final=True)
        self.assertIn(b"id: wire-id\r\nevent: message\r\nretry: 500\r\n", output)
        expanded = _events(output)[0]
        self.assertEqual(_text(expanded), self.value)
        self.assertEqual(expanded["actions"], value["actions"])
        self.assertEqual(expanded["id"], value["id"])

    async def test_unfinished_prefix_flushes_before_eof_done_error_or_tool_completion(
        self,
    ):
        for ending in (
            b"",
            b"data: [DONE]\n\n",
            _record({"error": "provider stopped"}),
            _record(
                {
                    "id": "response-1",
                    "invocationId": "invocation-1",
                    "author": "lllm_default_agent",
                    "content": {
                        "parts": [{"functionCall": {"name": "check", "args": {}}}]
                    },
                }
            ),
        ):
            with self.subTest(ending=ending):
                stream = CallbackTokenSseExpander(self.session_id)
                initial = _event(
                    "Before [encoded_callback_token ",
                    actions={"artifactDelta": {"one": 1}},
                )
                output = stream.feed(_record(initial), final=False)
                output += stream.feed(ending, final=True)
                events = _events(output)
                self.assertEqual(
                    "".join(_text(e) for e in events), "Before [encoded_callback_token "
                )
                self.assertEqual(sum(bool(e.get("actions")) for e in events), 1)

    async def test_unknown_malformed_and_overlong_tokens_are_literal(self):
        for text in (
            "[ordinary text]",
            "[encoded_callback_token invalid",
            "[encoded_callback_token " + "9" * 200,
            "[encoded_callback_token 999_999]",
        ):
            with self.subTest(text=text):
                stream = CallbackTokenSseExpander(self.session_id)
                output = b"".join(
                    stream.feed(_record(_event(char)), final=False) for char in text
                )
                output += stream.feed(b"", final=True)
                self.assertEqual("".join(_text(e) for e in _events(output)), text)

    async def test_other_session_cannot_expand_a_token(self):
        stream = CallbackTokenSseExpander("different-session")
        output = stream.feed(_record(_event(self.token, partial=False)), final=True)
        self.assertEqual(_text(_events(output)[0]), self.token)

    async def test_a_token_created_in_another_task_is_visible_after_an_earlier_lookup(
        self,
    ):
        # Bind and populate the output task's cache before the runner writes.
        self.assertEqual(
            expand_callback_tokens_for_session(self.token, self.session_id), self.value
        )

        async def producer():
            begin_callback_token_tracking()
            with patch("lllm.tools.callback_tokens.time.time", return_value=1234567):
                return store_callback_token(
                    "New token created after output started.", tool_context=self.context
                )["callback_token"]

        token = await asyncio.create_task(producer())
        stream = CallbackTokenSseExpander(self.session_id)
        output = stream.feed(_record(_event(token, partial=False)), final=True)
        self.assertEqual(
            _text(_events(output)[0]), "New token created after output started."
        )

    async def test_a_literal_token_inside_stored_text_is_not_expanded_twice(self):
        stored = "Literal nested reference: " + self.token
        outer = store_callback_token(stored, tool_context=self.context)[
            "callback_token"
        ]
        stream = CallbackTokenSseExpander(self.session_id)
        output = stream.feed(_record(_event(outer, partial=False)), final=True)
        self.assertEqual(_text(_events(output)[0]), stored)
        self.assertEqual(
            json.loads(
                expand_callback_token_output_body(
                    json.dumps({"text": outer}).encode(), self.session_id
                )
            )["text"],
            stored,
        )

    async def test_split_json_response_expands_but_binary_and_encoded_bodies_are_untouched(
        self,
    ):
        data = json.dumps(
            {"content": {"parts": [{"text": "日本語: " + self.token}]}},
            ensure_ascii=False,
        ).encode()
        for content_type, encoding in (
            (b"application/json", None),
            (b"application/octet-stream", None),
            (b"application/json", b"gzip"),
        ):
            with self.subTest(content_type=content_type, encoding=encoding):
                body = (
                    data if content_type == b"application/json" else b"\xff\x00" + data
                )
                headers = [
                    (b"content-type", content_type),
                    (b"content-length", str(len(body)).encode()),
                ]
                if encoding:
                    headers.append((b"content-encoding", encoding))

                async def app(scope, receive, send):
                    await receive()
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 200,
                            "headers": headers,
                        }
                    )
                    for index, byte in enumerate(body):
                        await send(
                            {
                                "type": "http.response.body",
                                "body": bytes([byte]),
                                "more_body": index < len(body) - 1,
                            }
                        )

                sent = await self._request(
                    app, path=f"/apps/app/users/user/sessions/{self.session_id}"
                )
                output = b"".join(m.get("body", b"") for m in sent)
                if content_type == b"application/json" and not encoding:
                    self.assertEqual(
                        json.loads(output)["content"]["parts"][0]["text"],
                        "日本語: " + self.value,
                    )
                    self.assertNotIn(b"content-length", dict(sent[0]["headers"]))
                else:
                    self.assertEqual(output, body)
                    self.assertEqual(sent[0]["headers"], headers)


if __name__ == "__main__":
    unittest.main()

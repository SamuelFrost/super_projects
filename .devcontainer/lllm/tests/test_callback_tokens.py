import unittest
from types import SimpleNamespace

from lllm.runtime_modifiers.tool_results import _replace_page_address_line
from lllm.runtime_modifiers.turn_guards import _skip_tools_when_stopping, begin_turn_outcome_tracking
from lllm.tools.callback_tokens import (
    _CALLBACK_TOKEN_CHARACTER_LIMIT,
    _callback_tokens_for_turn,
    _store_callback_token,
    _text_with_callback_tokens_expanded,
    list_stored_callback_tokens,
    preview_callback_token,
    recall_callback_token,
    store_callback_token,
)


class CallbackTokenTests(unittest.TestCase):
    def test_callback_token_reads_stored_text_when_an_agent_asks(self):
        begin_turn_outcome_tracking()
        address = "https://example.com/jobs/123"
        token = _store_callback_token(address)
        token_id = next(iter(_callback_tokens_for_turn.get()))
        browser_context = SimpleNamespace(agent_name="browser_agent", state={})
        root_context = SimpleNamespace(agent_name="lllm", state={})
        self.assertRegex(token_id, r"\d+_\d+")
        self.assertEqual(token, f"[encoded_callback_token {token_id}]")
        preview = {
            "id": token_id,
            "first_20_characters": address[:20],
            "last_20_characters": address[-20:],
            "character_count": len(address),
            "note": "",
            "description": "",
        }
        self.assertEqual(preview_callback_token(token_id, tool_context=browser_context), preview)
        self.assertEqual(preview_callback_token(token, tool_context=root_context), preview)
        self.assertEqual(
            recall_callback_token(token_id, tool_context=browser_context),
            {"id": token_id, "text": address},
        )
        self.assertEqual(recall_callback_token(token, tool_context=root_context), {"id": token_id, "text": address})
        stored = store_callback_token(
            address + "/again",
            note="listing",
            description="the job page",
            tool_context=browser_context,
        )
        self.assertTrue(stored["stored"])
        self.assertEqual(
            preview_callback_token(stored["callback_token"], tool_context=browser_context),
            {
                "id": stored["callback_token"].split(" ")[1].rstrip("]"),
                "first_20_characters": (address + "/again")[:20],
                "last_20_characters": (address + "/again")[-20:],
                "character_count": len(address + "/again"),
                "note": "listing",
                "description": "the job page",
            },
        )
        self.assertEqual(
            recall_callback_token(stored["callback_token"], tool_context=browser_context)["text"],
            address + "/again",
        )
        self.assertEqual(store_callback_token("short", tool_context=browser_context)["stored"], False)
        self.assertEqual(
            list_stored_callback_tokens(tool_context=browser_context)["stored_callback_tokens"],
            [
                {"id": token_id, "description": ""},
                {"id": stored["callback_token"].split(" ")[1].rstrip("]"), "description": "the job page"},
            ],
        )
        self.assertEqual(
            preview_callback_token("9", tool_context=root_context),
            {"id": "9", "missing": True},
        )
        recall_args = {"id": token}
        self.assertIsNone(
            _skip_tools_when_stopping(
                SimpleNamespace(name="preview_callback_token"), recall_args, browser_context
            )
        )
        self.assertEqual(recall_args["id"], token)
        delegated = {"request": token}
        self.assertIsNone(
            _skip_tools_when_stopping(
                SimpleNamespace(name="browser_agent"), delegated, root_context
            )
        )
        self.assertEqual(delegated["request"], address)
        file_args = {"path": token}
        self.assertIsNone(
            _skip_tools_when_stopping(
                SimpleNamespace(name="read_file"), file_args, root_context
            )
        )
        self.assertEqual(file_args["path"], address)

    def test_storage_stops_at_the_character_limit(self):
        begin_turn_outcome_tracking()
        import lllm.tools.callback_tokens as callback_tokens

        callback_tokens._CALLBACK_TOKEN_CHARACTER_LIMIT = 25
        try:
            first = store_callback_token("a" * 20, tool_context=SimpleNamespace(state={}))
            self.assertTrue(first["stored"])
            second = store_callback_token("b" * 20, tool_context=SimpleNamespace(state={}))
            self.assertEqual(
                second,
                {"stored": False, "reason": "callback token storage reached its character limit"},
            )
            self.assertTrue(
                store_callback_token("a" * 20, tool_context=SimpleNamespace(state={}))["stored"]
            )
        finally:
            callback_tokens._CALLBACK_TOKEN_CHARACTER_LIMIT = _CALLBACK_TOKEN_CHARACTER_LIMIT

    def test_text_shorter_than_twenty_characters_is_left_as_written(self):
        begin_turn_outcome_tracking()
        short_url = "https://x.gd/"
        self.assertLess(len(short_url), 20)
        page_line = f"2: URL短縮サービス X.gd ({short_url}) [selected]"
        shown_line, replaced_count = _replace_page_address_line(page_line)
        self.assertEqual(replaced_count, 0)
        self.assertEqual(shown_line, page_line)
        for length in range(0, 20):
            stored = ('a."b' * 6)[:length]
            self.assertIsNone(_store_callback_token(stored))
        stored = ('a."b' * 6)[:20]
        token = _store_callback_token(stored)
        tokens_by_id = _callback_tokens_for_turn.get()
        self.assertEqual([record["text"] for record in tokens_by_id.values()], [stored])
        self.assertRegex(next(iter(tokens_by_id)), r"^\d+_\d+$")
        expanded = _text_with_callback_tokens_expanded(f"value {token}.")
        self.assertEqual(expanded, f"value {stored}.")
        self.assertNotIn("[encoded_callback_token", expanded)
        for extra in (" extra", ":" + ("x" * 200)):
            unbounded = f"[encoded_callback_token 1_1700000000000{extra}]"
            self.assertEqual(_text_with_callback_tokens_expanded(unbounded), unbounded)

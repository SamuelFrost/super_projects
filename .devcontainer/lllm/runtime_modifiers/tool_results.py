"""Rewrite tool results before the model or the transcript reads them.

Browser snapshots and page lists often contain two hazards for local models:
1. Truncated percent-encoded URLs: Chrome DevTools can clip a long URL right
   through a multi-byte UTF-8 sequence (for example, cutting `%E9%A0%80` down
   to `%E9%A0%8`), leaving invalid UTF-8 that breaks navigation or search.
   This module trims the incomplete trailing codepoint and appends
   `[this URL was truncated]`.
2. Long `list_pages` URLs: Full query-string URLs eat context and are prone to
   copy errors when agents pass them around. This module stores each URL >= 20
   characters as an `[encoded_callback_token <number>_<timestamp>]` placeholder.

Both `prepare_model_tool_results` (before the model sees the request) and
`tool_result_display` (when `--outputChannels` prints `tool_results`) run these
same transformations so the terminal transcript matches the model's view and
reports rewrite counts in the header (e.g. `[list_pages repair_truncated_utf8 1 encoded_callback_token 2 result]`).
"""

import re

from lllm.tools.callback_tokens import store_callback_token

_HEX_DIGIT = set("0123456789abcdefABCDEF")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'`]+")
_TRUNCATED_URL_NOTE = " [this URL was truncated]"
_REPAIR_TRUNCATED_UTF8 = "repair_truncated_utf8"
_CALLBACK_TOKEN_REWRITE = "encoded_callback_token"


def is_image_payload(value: dict) -> bool:
    type_name = str(value.get("type") or "")
    mime_type = str(value.get("mimeType") or value.get("mime_type") or "")
    return type_name == "image" or mime_type.startswith("image/")


def _percent_encoded_byte(text: str, index: int) -> int | None:
    if index + 2 >= len(text) or text[index] != "%":
        return None
    first_hex, second_hex = text[index + 1], text[index + 2]
    if first_hex not in _HEX_DIGIT or second_hex not in _HEX_DIGIT:
        return None
    return int(first_hex + second_hex, 16)


def _utf8_sequence_length(lead_byte: int) -> int | None:
    if lead_byte < 0x80:
        return 1
    if 0xC2 <= lead_byte <= 0xDF:
        return 2
    if 0xE0 <= lead_byte <= 0xEF:
        return 3
    if 0xF0 <= lead_byte <= 0xF4:
        return 4
    return None


def _incomplete_percent_escape_length(text: str) -> int:
    if text.endswith("%"):
        return 1
    if (
        len(text) >= 2
        and text[-2] == "%"
        and text[-1] in _HEX_DIGIT
        and (len(text) < 3 or text[-3] != "%")
    ):
        return 2
    return 0


def _percent_encoded_run_ending_at(text: str, encoded_end: int) -> tuple[int, bytearray]:
    run_start = encoded_end
    while run_start >= 3 and _percent_encoded_byte(text, run_start - 3) is not None:
        run_start -= 3
    encoded_bytes = bytearray()
    cursor = run_start
    while cursor + 3 <= encoded_end:
        encoded_byte = _percent_encoded_byte(text, cursor)
        if encoded_byte is None:
            break
        encoded_bytes.append(encoded_byte)
        cursor += 3
    return run_start, encoded_bytes


def _unfinished_utf8_byte_index(encoded_bytes: bytearray) -> int | None:
    """Return the byte offset where a trailing UTF-8 sequence is incomplete or invalid."""
    byte_index = 0
    while byte_index < len(encoded_bytes):
        sequence_length = _utf8_sequence_length(encoded_bytes[byte_index])
        if sequence_length is None or byte_index + sequence_length > len(encoded_bytes):
            return byte_index
        try:
            bytes(encoded_bytes[byte_index : byte_index + sequence_length]).decode("utf-8")
        except UnicodeDecodeError:
            return byte_index
        byte_index += sequence_length
    return None


def truncated_url_cut_index(url: str) -> int | None:
    """Return the string index where a trailing percent-encoded UTF-8 sequence was cut off.

    Only inspects the contiguous run of `%XX` bytes at the very end of the URL
    (plus any dangling `%` or `%X` suffix), so valid percent signs or complete
    escapes earlier in the URL are untouched.
    """
    incomplete_escape_length = _incomplete_percent_escape_length(url)
    encoded_end = len(url) - incomplete_escape_length
    run_start, encoded_bytes = _percent_encoded_run_ending_at(url, encoded_end)
    unfinished_byte_index = _unfinished_utf8_byte_index(encoded_bytes)
    if unfinished_byte_index is not None:
        return run_start + unfinished_byte_index * 3
    if incomplete_escape_length == 2:
        return encoded_end
    if incomplete_escape_length == 1 and encoded_bytes:
        return encoded_end
    return None


def _repair_truncated_utf8_url(url: str) -> str:
    # list_pages writes `title (url)`, and the match includes that closing paren.
    url_body, closing_paren = (url[:-1], ")") if url.endswith(")") else (url, "")
    cut_index = truncated_url_cut_index(url_body)
    if cut_index is None:
        return url
    complete_prefix = url_body[:cut_index].rstrip("%")
    return complete_prefix + _TRUNCATED_URL_NOTE + closing_paren


def _repair_truncated_utf8_in_value(value) -> tuple[object, int]:
    if isinstance(value, str):
        repaired_url_count = 0

        def repair_url(url_match):
            nonlocal repaired_url_count
            repaired = _repair_truncated_utf8_url(url_match.group(0))
            if repaired != url_match.group(0):
                repaired_url_count += 1
            return repaired

        return _URL_IN_TEXT.sub(repair_url, value), repaired_url_count
    if isinstance(value, list):
        repaired_items = []
        repaired_url_count = 0
        for item in value:
            repaired_item, item_count = _repair_truncated_utf8_in_value(item)
            repaired_items.append(repaired_item)
            repaired_url_count += item_count
        return repaired_items, repaired_url_count
    if isinstance(value, dict):
        if is_image_payload(value):
            return value, 0
        repaired = {}
        repaired_url_count = 0
        for key, item in value.items():
            repaired_item, item_count = _repair_truncated_utf8_in_value(item)
            repaired[key] = repaired_item
            repaired_url_count += item_count
        return repaired, repaired_url_count
    return value, 0


def _repair_truncated_utf8_in_tool_results(llm_request) -> None:
    """Cut a tool-result URL that ends mid-character. Leave complete encoding as written."""
    for message_content in llm_request.contents or []:
        for part in message_content.parts or []:
            function_response = part.function_response
            if function_response is None or function_response.response is None:
                continue
            repaired, repaired_url_count = _repair_truncated_utf8_in_value(
                function_response.response
            )
            if repaired_url_count:
                function_response.response = repaired


def _has_numeric_page_id(page_id) -> bool:
    """list_pages entry ids are numbers. Callback token ids are separate."""
    if isinstance(page_id, bool):
        return False
    if isinstance(page_id, int):
        return True
    return isinstance(page_id, str) and page_id.isdigit()


def _token_for_page_address(url_body: str) -> str | None:
    """Store a page address. A truncation note stays on the shown line and on the token."""
    suffix = ""
    if url_body.endswith(_TRUNCATED_URL_NOTE):
        url_body = url_body[: -len(_TRUNCATED_URL_NOTE)].rstrip()
        suffix = _TRUNCATED_URL_NOTE
    stored = store_callback_token(url_body, note=suffix.strip())
    if not stored.get("stored"):
        return None
    return stored["callback_token"] + suffix


def _replace_page_address_line(line: str) -> tuple[str, int]:
    """Replace a URL in one `list_pages` text line with a callback token.

    Handles both titled lines (`1: Page Title (https://...) [selected]`) and
    bare URL lines (`2: https://...`), adding an explicit `url:` prefix so the
    model knows the token stands for the page address.
    """
    page_match = re.match(r"^(\d+): (.*)$", line)
    if page_match is None:
        return line, 0
    page_id, rest = page_match.groups()
    wrapped_url_start = max(rest.rfind(" (http://"), rest.rfind(" (https://"))
    if wrapped_url_start >= 0:
        closing_paren = rest.rfind(")")
        if closing_paren > wrapped_url_start:
            title = rest[:wrapped_url_start]
            url_body = rest[wrapped_url_start + 2 : closing_paren]
            suffix = rest[closing_paren + 1 :]
            shown = _token_for_page_address(url_body)
            if shown is None:
                return line, 0
            return f"{page_id}: {title} (url: {shown}){suffix}", 1
    bare_url = re.match(r"(https?://\S+)(.*)$", rest)
    if bare_url is None:
        return line, 0
    url_body, suffix = bare_url.groups()
    shown = _token_for_page_address(url_body)
    if shown is None:
        return line, 0
    return f"{page_id}: url: {shown}{suffix}", 1


def _replace_page_addresses_in_text(text: str) -> tuple[str, int]:
    replaced_lines = []
    replaced_count = 0
    for line in text.split("\n"):
        replaced_line, line_count = _replace_page_address_line(line)
        replaced_lines.append(replaced_line)
        replaced_count += line_count
    return "\n".join(replaced_lines), replaced_count


def _replace_page_addresses_in_value(value) -> tuple[object, int]:
    if isinstance(value, str):
        return _replace_page_addresses_in_text(value)
    if isinstance(value, list):
        replaced_items = []
        replaced_count = 0
        for item in value:
            replaced_item, item_count = _replace_page_addresses_in_value(item)
            replaced_items.append(replaced_item)
            replaced_count += item_count
        return replaced_items, replaced_count
    if isinstance(value, dict):
        if is_image_payload(value):
            return value, 0
        has_page_id = _has_numeric_page_id(value.get("id")) if "url" in value else False
        replaced = {}
        replaced_count = 0
        for key, item in value.items():
            if (
                key == "url"
                and has_page_id
                and isinstance(item, str)
                and item.startswith(("http://", "https://"))
            ):
                shown = _token_for_page_address(item)
                if shown is None:
                    replaced[key] = item
                    continue
                replaced[key] = shown
                replaced_count += 1
                continue
            replaced_item, item_count = _replace_page_addresses_in_value(item)
            replaced[key] = replaced_item
            replaced_count += item_count
        return replaced, replaced_count
    return value, 0


def _replace_page_addresses_in_tool_results(llm_request) -> int:
    """Hide list_pages addresses behind callback tokens."""
    replaced_count = 0
    for message_content in llm_request.contents or []:
        for part in message_content.parts or []:
            function_response = part.function_response
            if (
                function_response is None
                or function_response.name != "list_pages"
                or function_response.response is None
            ):
                continue
            replaced, item_count = _replace_page_addresses_in_value(
                function_response.response
            )
            replaced_count += item_count
            if item_count:
                function_response.response = replaced
    return replaced_count


def tool_result_display(tool_name: str, tool_response: object) -> tuple[str, object]:
    """The tool result the transcript shows, with the same rewrites the model sees."""
    rewritten, repaired_url_count = _repair_truncated_utf8_in_value(tool_response)
    replaced_count = 0
    if tool_name == "list_pages":
        rewritten, replaced_count = _replace_page_addresses_in_value(rewritten)
    display_name = tool_name
    if repaired_url_count:
        display_name = f"{display_name} {_REPAIR_TRUNCATED_UTF8} {repaired_url_count}"
    if replaced_count:
        display_name = f"{display_name} {_CALLBACK_TOKEN_REWRITE} {replaced_count}"
    return display_name, rewritten


def prepare_model_tool_results(llm_request) -> None:
    """Apply the tool-result rewrite to every tool result already on the request."""
    _repair_truncated_utf8_in_tool_results(llm_request)
    _replace_page_addresses_in_tool_results(llm_request)

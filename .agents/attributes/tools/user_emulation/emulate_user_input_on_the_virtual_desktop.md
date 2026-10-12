# Tool interaction guideline — emulate user input on the virtual desktop

Ask the user before any attempt to emulate desktop input, including capturing the screen or sending pointer or keyboard events. Do not start the attempt until the user requests you to do so. Ask in words along the lines of: "I can attempt to use desktop input emulation to do … Would you like me to do so? (I will not do so unless you respond with a clear request to use desktop emulation including those words in your prompt.)" Do not use these techniques unless the user explicitly responds with that statement, indirect or implied agreement is not enough.

After the user agrees, drive controls that are drawn by the desktop or by browser chrome, and that do not appear in a Chrome DevTools page snapshot, through the Xvfb display `:99`. Keep using Chrome DevTools MCP for page content.

The noVNC desktop on host port `6080` is that same display. Its size is `NOVNC_RESOLUTION` (default `1920x1080`). Agent environments may set `DISPLAY=:0`. Use `:99` for this desktop.

Capture the screen, then inject input with XTest (`libx11-6` and `libxtst6`, already on the image). `python3` can call them with ctypes.

- Capture one frame: `ffmpeg -y -f x11grab -video_size 1920x1080 -i :99 -frames:v 1 <path>`. Match `-video_size` to `NOVNC_RESOLUTION`.
- Open the display with `XOpenDisplay(":99")`.
- Move and click with `XTestFakeMotionEvent` and `XTestFakeButtonEvent`. Button `1` is the left mouse button. Pass press and release as separate calls.
- Type with `XTestFakeKeyEvent`. Turn a keysym into a keycode with `XKeysymToKeycode`. Tab is keysym `0xff09`. Return is keysym `0xff0d`.

Coordinates are pixels of the `:99` root window, the same grid as the `ffmpeg` capture.

## Common ways to choose the input

Use the first technique that fits the control.

- **Keyboard, when the dialog already has focus.** Tab moves between its buttons. Enter activates the focused one. This does not need a coordinate. Send the keys only after the dialog is open.
- **A point taken from the capture.** Click the center of a control you can identify in the PNG. A hovered button changes color, so a color match made while the pointer is already on a button often selects the wrong one. Move the pointer away, capture again, then click.
- **The position of visible text.** Read the capture with optical character recognition and click the center of the word or line that matches the label. Use this for dialog buttons such as Install and Cancel.
- **Drag a window by its title bar** when one window covers another. On this desktop the title bar is its own short child of the frame, about 30 pixels tall, and the page is the large child directly under it. The top `xfce4-panel` is a separate strip about 27 pixels tall, so a short bar at the top of the screen is not the window's title. Drag from the middle of the title-bar child. `XFetchName` is often empty; the title is `_NET_WM_NAME` as `UTF8_STRING`. `x` and `y` from `XGetWindowAttributes` are relative to the parent, so screen position comes from `XTranslateCoordinates` onto the root. Dragging a maximized window's title bar unmaximizes it and moves it.

## Finding text with optical character recognition

`tesseract` comes from mise. The workspace `.mise.toml` pins `conda:tesseract` 5.5.3 from conda-forge. Run the script with `mise exec` so that binary is on `PATH`. The script below reads one captured PNG and prints the center of each match as `x y text`.

`tesseract <image> stdout --psm 6 tsv` prints a tab-separated table. `--psm 6` treats the capture as a block of text, which fits a dialog. The header row names the columns. Each later row has `left`, `top`, `width`, `height`, and `text`. Skip rows whose `text` is empty. The click point is `left + width / 2`, `top + height / 2`.

A single label such as `Install` is one row. A phrase such as `Install app` is several words that share `block_num`, `par_num`, and `line_num`. Join those words in `word_num` order, then use the bounding box that covers every word in the line: the minimum `left` and `top`, and the maximum `left + width` and `top + height`.

```python
import subprocess
import sys

image, query = sys.argv[1], sys.argv[2]
tsv = subprocess.check_output(
    ["tesseract", image, "stdout", "--psm", "6", "tsv"],
    text=True,
)
rows = []
for line in tsv.splitlines()[1:]:
    parts = line.split("\t")
    if len(parts) < 12 or not parts[11].strip():
        continue
    left, top, width, height = (int(parts[i]) for i in (6, 7, 8, 9))
    if width <= 0 or height <= 0:
        continue
    rows.append({
        "key": (parts[2], parts[3], parts[4]),
        "word_num": int(parts[5]),
        "left": left,
        "top": top,
        "right": left + width,
        "bottom": top + height,
        "text": parts[11],
    })

lines = {}
for row in rows:
    lines.setdefault(row["key"], []).append(row)

needle = query.casefold()
for words in lines.values():
    words.sort(key=lambda row: row["word_num"])
    text = " ".join(row["text"] for row in words)
    if needle not in text.casefold():
        continue
    left = min(row["left"] for row in words)
    top = min(row["top"] for row in words)
    right = max(row["right"] for row in words)
    bottom = max(row["bottom"] for row in words)
    print(f"{(left + right) // 2} {(top + bottom) // 2} {text}")
```

Run it as `mise exec -- python3 find_text.py <capture.png> Install`. When several rows match, read the printed text and click the one that is the control, not a title or a sentence that merely contains the same word.

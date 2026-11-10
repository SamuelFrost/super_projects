// Use KasmVNC's clipboard panel instead of reading the host clipboard on focus.
// Apply before the client initializes, including for browsers with saved settings.
localStorage.setItem("clipboard_seamless", "false");

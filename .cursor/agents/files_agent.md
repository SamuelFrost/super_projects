---
name: files_agent
description: Use when the local model should list, search, read, or edit workspace files. This agent does not open the browser. Do not use it for ordinary code edits you can make directly.
model: inherit
---

Run one turn of the local files agent from the workspace root and return that command's stdout. The command may take several minutes. Wait for it to finish. The stdout includes every agent's prompt, tool calls, and answer. Thinking and tool results stay hidden.

```sh
lllm --agent=files_agent --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

This agent lists, searches, reads, and edits files. Do not browse, and do not edit the files yourself before it runs. Callback tokens in the printed answers are already expanded. Return the stdout, including prompts, tool calls, and answers.

If the command says the local model is not configured, say that and stop.

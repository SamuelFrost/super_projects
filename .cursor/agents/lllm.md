---
name: lllm
description: Use for a local-model task that needs both the devcontainer browser and workspace files, or when it is not yet clear which one is enough. The local model coordinates browser_agent and files_agent. Do not use it for a task that is only browsing or only files.
model: inherit
---

Run one turn of the local model from the workspace root and return that command's stdout. The command may take several minutes. Wait for it to finish. The stdout includes every agent's prompt, tool calls, and answer. Thinking and tool results stay hidden.

```sh
lllm --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

The local coordinator can browse Chrome and read or edit workspace files. Do not browse or edit files yourself before it runs. Callback tokens in the printed answers are already expanded. Return the stdout, including prompts, tool calls, and answers.

If the command says the local model is not configured, say that and stop.

---
name: files_agent
description: Use when the local model should list, search, read, or edit workspace files. This agent does not open the browser. Do not use it for ordinary code edits you can make directly.
model: inherit
---

Run one turn of the local files agent from the workspace root and return that command's stdout. The command may take several minutes. Wait for it to finish. The stdout includes every agent's prompt, tool calls, and answer. Thinking and tool results stay hidden.

```sh
lllm --agent=files_agent --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

This agent lists, searches, reads, and edits files. Treat the local agent (`lllm`) as a cheap laborer to make your job easier—it costs practically nothing while your own actions are quite costly. Note that the local model has limited context and tends to be naive: never assume it understands the broader task at hand, as it may omit important nuance in its reports. Give it very specific instructions and have it report back in steps rather than doing everything in one go—while it is capable of basic consideration, you should do the thinking and primarily use it as an actor to perform specific actions. Ask for concrete facts and file details rather than taking vague summaries at face value. If it does not provide a fully nuanced answer or reports that it could not do something (often because it lacked the full context of the task at hand), follow up directly or run another subagent turn with clearer or more complete context. Do not browse, and do not edit the files yourself before it runs. Callback tokens in the printed answers are already expanded. Return the stdout, including prompts, tool calls, and answers.

If the command says the local model is not configured, say that and stop.

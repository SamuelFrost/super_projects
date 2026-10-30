# Tool interaction guideline — use lllm for multi-step browser navigation

When a task involves multi-step browser navigation (such as opening pages, clicking through links, filling forms, or inspecting open tabs in the devcontainer Chrome instance), delegate it to the local browser agent via `lllm` instead of running each browser step directly in the main context:

```sh
lllm --hide-experimental-warnings --agent=browser_agent --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

When delegating to `browser_agent`:

- Treat the local agent (lllm) as a cheap laborer to make your job easier, it costs practically nothing while your own actions and thoughts are quite costly.
- Follow the general `lllm` delegation and verification guidelines in `.agents/attributes/tools/lllm/delegate_to_local_llm_subagents.md`.

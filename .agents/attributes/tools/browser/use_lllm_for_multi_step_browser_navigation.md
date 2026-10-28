# Tool interaction guideline — use lllm for multi-step browser navigation

When a task involves multi-step browser navigation (such as opening pages, clicking through links, filling forms, or inspecting open tabs in the devcontainer Chrome instance), delegate it to the local browser agent via `lllm` instead of running each browser step directly in the main context:

```sh
lllm --agent=browser_agent --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

When writing `<the task>` prompt:

- Provide clear, concrete details on the scope of the task (target URLs or tabs, specific actions to take, and boundaries on what not to modify or submit).
- Explicitly state when the agent should stop and report back (for example, once specific information is found, before submitting a final form, or if a login wall, unexpected page state, or blocker is reached), along with the exact details to include in the report.
- Do the high-level thinking yourself and use the local agent primarily as an actor to perform specific, step-by-step actions rather than expecting it to think and complete a complex workflow all in one go.
- Account for the local model's tendency to be naive: never assume it understands the broader task at hand. It may omit important nuance in its reports or uncritically accept inaccurate, outdated, or misleading information found on the internet. Ask for concrete evidence (exact quotes, URLs, page titles, or observed UI states) rather than taking vague summaries at face value.
- Follow up directly with the Chrome DevTools MCP or spawn another subagent call with clearer, more complete context if the agent does not provide a sufficiently nuanced answer or reports that it could not complete something (this is often because the subagent lacked the full context of the task at hand rather than the action being impossible).
- Treat the local agent (lllm) as a cheap laborer to make your job easier, it costs practically nothing while your own actions and thoughts are quite costly.

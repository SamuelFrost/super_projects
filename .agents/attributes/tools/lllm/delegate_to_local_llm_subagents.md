# Tool interaction guideline — delegate to local LLM subagents

- Treat the local agent (lllm) as a cheap laborer to make your job easier, it costs practically nothing while your own actions and thoughts are quite costly.
- Choose the agent that matches the level of control you want: `--agent=browser_agent` for direct orders over `browser_agent`, `--agent=files_agent` for direct orders over `files_agent`, or the default root `lllm_default_agent` agent for general tasks, thinking, and coordinating the finer details of interactions with the subagents:
  ```sh
  lllm --hide-experimental-warnings --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
  ```
- When writing `<the task>` prompt and evaluating its output:
  - Provide clear, concrete details on the scope of the task (target URLs, tabs, or file paths, specific actions to take, and explicit boundaries on which domains, paths, links, or submissions are off-limits).
  - Explicitly state when the agent should stop and report back (for example, once specific information is found, before submitting a final form, or if a login wall, unexpected state, or blocker is reached), along with the exact deliverables to include in the report.
  - Do the high-level thinking yourself and use the local agent primarily as an actor to perform specific, step-by-step actions rather than expecting it to think and complete a complex workflow all in one go.
  - Account for the local model's tendency to be naive: never assume it understands the broader task at hand. It may omit important nuance in its reports or uncritically accept inaccurate, outdated, or misleading information. Ask for concrete evidence (exact quotes, file paths, URLs, page titles, or observed states) rather than taking vague summaries at face value.
  - Do not blindly accept subagent conclusions: verify that every claim is backed by verbatim observations from the target state and a verified state change after actions. Treat tool errors, empty returns, or negative claims without supporting state quotes as unverified attempts rather than findings; when a report is unverified, contradictory, or out of scope, redirect the subagent by specifying the exact missing observation or discrepancy while leaving tool selection to the subagent.
  - Follow up directly with your own tools or spawn another `lllm` call with clearer, more complete context if the agent does not provide a sufficiently nuanced answer or reports that it could not complete something (this is often because the subagent lacked the full context of the task at hand rather than the action being impossible). A follow-up repeats `--agent` and passes `--session` from the previous `lllm session:` line. The new prompt names the missing observation.
  - When `LLLM_LOG_DIR` or `--log-dir` is set, `lllm` automatically writes each turn's transcript to `log_<YYYY-MM-DDTHHMMSSZ>_<agent>.txt` in that directory.

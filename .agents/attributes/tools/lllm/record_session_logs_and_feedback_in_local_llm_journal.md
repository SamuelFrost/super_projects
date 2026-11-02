# Tool interaction guideline — record local LLM session logs and feedback in local_llm_journal

- After each use of the local agent, write coordinator feedback in `.devcontainer/lllm/.local_only/local_llm_journal/feedback(from_AI_coordinator)/`. `lllm` writes the whole session to `.devcontainer/lllm/.local_only/local_llm_journal/session_transcripts/<app>/<session id>/transcript.txt` unless `--log-dir` or `LLLM_LOG_DIR` selects another directory. CLI and `lllm web` both update that file from `.devcontainer/lllm/.adk/session.db`. Do not copy those files by hand. Follow `standard_workflow.md` in that journal.

```sh
lllm --hide-experimental-warnings --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

A follow-up repeats `--agent` and adds `--session` from the `lllm session:` line printed on stderr.

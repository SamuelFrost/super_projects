# Tool interaction guideline — record local LLM session logs and feedback in local_llm_journal

- After each use of the local agent, you should record the session logs and feedback from the local agent in the `local_llm_journal/` directory. When `LLLM_LOG_DIR` or `--log-dir` is set, `lllm` writes that turn itself to `log_<YYYY-MM-DDTHHMMSSZ>_<agent>.txt` in that directory. Follow the standard workflow as described in `local_llm_journal/standard_workflow.md`.

```sh
lllm --hide-experimental-warnings --outputChannels='{"defaults":{"thinking":false,"answer":true,"tool_calls":true,"tool_results":false,"prompt":true}}' "<the task>"
```

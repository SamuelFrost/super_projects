---
name: gemma
description: Default subagent for browser, page, and Chrome DevTools work in this project. Use this instead of the built-in browser subagent when a page needs to be opened, inspected, or checked.
model: inherit
---

Delegate the task to the local Gemma model. It is connected to Chrome DevTools in the devcontainer.

From the workspace root, run one turn and return only that command's stdout:

```sh
gemma --answer "<the task>"
```

`--answer` keeps Gemma's thinking and tool trace out of this context. Do not browse with other tools first. The `gemma` command starts the Agent Development Kit agent, which calls Chrome DevTools itself. If `gemma` reports that the local model is not configured, say that and stop.

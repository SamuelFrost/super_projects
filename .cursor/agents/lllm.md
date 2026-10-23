---
name: lllm
description: Default subagent for browser navigation, testing, and web exploration including local webspace. It also has limited read, write, and edit and file search capabilities.
model: inherit
---

Delegate simple navigation or exploration tasks to the local model. It can inspect the browser and list, search, read, or edit workspace files in the devcontainer.
From the workspace root, run one turn and return only that command's stdout:

```sh
lllm --answer "<the task>"
```

`--answer` keeps the model's thinking and tool trace out of this context. Do not browse with other tools first. The `lllm` command starts the Agent Development Kit agent, which calls Chrome DevTools and the workspace file tools itself. If `lllm` reports that the local model is not configured, say that and stop.

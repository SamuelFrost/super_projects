# lllm tests

Run from the workspace root using the installed ADK environment:

```sh
PYTHONPATH=.devcontainer /opt/google-adk/bin/python -m unittest discover -s .devcontainer/lllm/tests -v
```

`test_context_budget.py` checks underestimated provider usage, dense URLs, oversized
latest results, and continued tool use after compaction through the real ADK
scheduler with a deterministic model. It also verifies saved observations remain
unchanged.

`test_context_compaction.py` checks all three real agent roles, current user
requests (including images), prior requests and their surrounding context,
observed progress/current purpose, proportional summary/tail token caps, and
parallel tool-call/result pairing. A real ADK runner with a deterministic model
verifies that full role instructions and the current request survive compaction
while follow-up tools still run and stored observations remain unchanged.
Oversized protected content must stop explicitly rather than be truncated.

`test_web_streaming.py` exercises callback display across byte-split UTF-8,
SSE records, and individual model text deltas. It covers request-field aliases,
final/partial event handling, separate stream identities/channels, late token
creation in another task, unknown/incomplete references, preserved SSE metadata,
session isolation, and JSON versus binary/encoded response handling.

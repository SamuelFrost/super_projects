# lllm tests

Run from the workspace root using the installed ADK environment:

```sh
PYTHONPATH=.devcontainer /opt/google-adk/bin/python -m unittest discover -s .devcontainer/lllm/tests -v
```

`test_context_budget.py` checks underestimated provider usage, dense URLs, oversized
latest results, and continued tool use after compaction through the real ADK
scheduler with a deterministic model. It also verifies saved observations remain
unchanged.

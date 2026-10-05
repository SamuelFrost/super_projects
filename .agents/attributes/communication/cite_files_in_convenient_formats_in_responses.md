# Communication guideline — cite files in convenient formats in responses

- Cite relevant files relative to the workspace directory (e.g. `sample_app_1/docker-compose.yml` instead of `/workspace/sample_app_1/docker-compose.yml`)
- Do not use `file://` as it will not work in devcontainer environments
- Do not use `/workspaces/` as it will not work on the host machine or if the workspace name is modified
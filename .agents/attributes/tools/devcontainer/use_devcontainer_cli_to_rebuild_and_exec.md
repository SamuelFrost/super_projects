# Tool interaction guideline — recreate the target devcontainer after setup changes and exec into it with the CLI

When modifying `.devcontainer/Dockerfile`, `.devcontainer/compose.yaml`, `.devcontainer/devcontainer.json`, or otherwise changing the setup of a target devcontainer, apply the configuration change and then recreate the container from the workspace folder that owns that `.devcontainer/`:

```sh
docker compose -f .devcontainer/compose.yaml down
devcontainer up
```

When you need to execute something inside that container, use `devcontainer exec` rather than assuming the current shell is already inside it.

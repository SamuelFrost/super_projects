# Compose apps within the devcontainer at `http://localhost:<port>`

Chrome and `chrome-devtools-mcp` run inside the super_projects devcontainer. A docker compose stack within the devcontainer publishes its `ports:` on the **Docker host**, so `http://localhost:<port>` works on the host but not on `127.0.0.1` inside this container until something forwards it.

The `localhost_forward_proxy` Compose sidecar (`.devcontainer/scripts/localhost_forward_proxy`) does that:

1. Watches the Docker socket for containers whose Compose `working_dir` is under the workspace (`/${SUPER_PROJECTS_WORKDIR:-workspaces}` inside the container, or `HOST_WORKSPACE_DIR` on the host), skipping the devcontainer's own Compose project.
2. Attaches the `devcontainer` container to that stack's Compose network when it is not on it yet. This is also what makes the Compose service name resolve from the devcontainer (for example `http://sample_app_1/`).
3. Listens on `127.0.0.1:<hostPort>` for every published TCP port and forwards connections to the container's private port. The sidecar shares the devcontainer's network namespace, so Chrome in the devcontainer sees those listeners as its own localhost.

Open the same URL you would use on the host, for example `http://localhost:3000`.

The sidecar starts with `.devcontainer/compose.yaml` (`devcontainer up`), reacts to container start/stop events, and re-checks every 15 seconds.

## What you need in the project

A normal Compose `ports:` entry for the port you want in the browser:

```yaml
ports:
  - "3000:80"
```

No parent network, forwarder config, or Rails `config.hosts` entry is needed for `localhost`.

## Notes

- A host port that is already in use inside the devcontainer (noVNC `6080`, VNC `5900`, Chrome debugging `9223`) is skipped and reported in the sidecar log; it is retried once the port is free.
- `docker compose down` in the app may print `Network <project>_default Resource is still in use`: the devcontainer stays attached to that network so the forward can come back on the next `compose up`, which reuses the network. The command still exits 0.

## Troubleshooting

From the workspace (host or devcontainer):

```sh
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml logs -f localhost_forward_proxy
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml stop localhost_forward_proxy
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml start localhost_forward_proxy
```

The log lists the active forwards as `<hostPort>→<container>:<privatePort>` whenever they change. Unit tests: `mise test` in `.devcontainer/scripts/localhost_forward_proxy`.

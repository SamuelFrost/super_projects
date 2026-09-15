# Compose apps within the devcontainer at `http://localhost:<port>`

Chrome and `chrome-devtools-mcp` run inside the super_projects devcontainer. A docker compose stack within the devcontainer publishes its `ports:` mapping on the **host**, so that URL does not exist on `127.0.0.1` inside this container until something bridges it.

The `localhost_forward_proxy` Compose sidecar (`.devcontainer/scripts/localhost_forward_proxy`) does that automatically:

1. Finds running containers that belong to this workspace (Compose `working_dir` or bind mounts under the workspace path, including `/workspaces`).
2. Attaches the **parent** `devcontainer` to that stack's Compose network (no change to the project's Compose file). `docker compose down` may report that network is still in use while the parent remains attached; `compose up` reuses it.
3. Forwards `127.0.0.1:<hostPort>` to the container's private port (Ruby TCP proxy). It shares the parent's network namespace, so Chrome in the parent sees the same loopback.

Open the same URL you would use on the host, for example `http://localhost:3000`.

The sidecar starts with the rest of `.devcontainer/compose.yaml` and reacts to later `docker compose up` / `down`. It uses the parent container's identity, so company forks that rename `super_projects_default` keep working.

## What you need in the project

A normal Compose `ports:` entry for the port you want in the browser:

```yaml
ports:
  - "3000:80"
```

Do not add the parent network, a forwarder config file, or a Rails `config.hosts` workaround for the container DNS name.

Two apps that publish the same host port collide here the same way they do on the host; the first match is kept and the other is logged.

## Troubleshooting

From the workspace (host or parent container):

```sh
docker compose -f .devcontainer/compose.yaml logs -f localhost_forward_proxy
docker compose -f .devcontainer/compose.yaml stop localhost_forward_proxy
docker compose -f .devcontainer/compose.yaml start localhost_forward_proxy
```

`docker compose down` may print `Network sample_app_1_default Resource is still in use`. The parent stays on that network so the forward can reach the app; the next `compose up` reuses it. Do not `docker network disconnect` that from *inside* the parent (it can hang the Docker API).

Ports already used in this container (noVNC `6080`, VNC `5900`, Chrome debugging `9223`, and this container's own published ports) are not mirrored.

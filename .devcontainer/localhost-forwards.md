# Compose apps within the devcontainer at `http://localhost:<port>`

Chrome and `chrome-devtools-mcp` run inside the super_projects devcontainer. A docker compose stack within the devcontainer publishes its `ports:` mapping on the **host**, so that URL does not exist on `127.0.0.1` inside this container until something bridges it.

`start-localhost-forwards` (`.devcontainer/scripts/dockerfile/localhost-forward.sh`) does that automatically:

1. Finds running containers that belong to this workspace (Compose `working_dir` or bind mounts under the workspace path, including `/workspaces`).
2. Attaches **this** container to that stack's Compose network (no change to the project's Compose file). `docker compose down` may report that network is still in use while this container remains attached; `compose up` reuses it.
3. Forwards `127.0.0.1:<hostPort>` to the container's private port (`socat`, or a Python TCP proxy if `socat` is not in the image yet).

Open the same URL you would use on the host, for example `http://localhost:3000`.

The watcher starts with the container (`compose.yaml` and `postStartCommand`) and reacts to later `docker compose up` / `down`. It uses this container's identity, so company forks that rename `super_projects_default` keep working.

## What you need in the project

A normal Compose `ports:` entry for the port you want in the browser:

```yaml
ports:
  - "3000:80"
```

Do not add the parent network, a forwarder config file, or a Rails `config.hosts` workaround for the container DNS name.

Two apps that publish the same host port collide here the same way they do on the host; the first match is kept and the other is logged.

## Troubleshooting

- Status: `bash /workspaces/.devcontainer/scripts/dockerfile/localhost-forward.sh once`
- Watcher log: `/tmp/localhost-forward-watcher.log`
- Per-port logs: `/tmp/localhost-forward-<port>.log`
- Restart: the same script with no arguments (or reconnect the devcontainer)
- Stop: `bash /workspaces/.devcontainer/scripts/dockerfile/localhost-forward.sh stop`

`docker compose down` may print `Network sample_app_1_default Resource is still in use`. The parent stays on that network so the forward can reach the app; the next `compose up` reuses it. Do not `docker network disconnect` that from *inside* the parent (it can hang the Docker API).

Ports already used in this container (noVNC `6080`, VNC `5900`, Chrome debugging `9223`, and this container's own published ports) are not mirrored.

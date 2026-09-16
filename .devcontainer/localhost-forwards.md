# Compose apps within the devcontainer at `http://localhost:<port>`

Chrome and `chrome-devtools-mcp` run inside the super_projects devcontainer. A docker compose stack within the devcontainer publishes its `ports:` on the **Docker host**, so `http://localhost:<port>` works on the host but not on `127.0.0.1` inside this container until something forwards it.

The `localhost_forward_proxy` Compose sidecar does that. It starts with `.devcontainer/compose.yaml` (`devcontainer up`). Open the same URL you would use on the host, for example `http://localhost:3000`.

## What you need in the project

A normal Compose `ports:` entry for the port you want in the browser:

```yaml
ports:
  - "3000:80"
```

No parent network, forwarder config, or Rails `config.hosts` entry is needed for `localhost`.

How it works, resource use, and limits: [`.devcontainer/scripts/localhost_forward_proxy/.directory_information.md`](scripts/localhost_forward_proxy/.directory_information.md).

## Troubleshooting

From the workspace (host or devcontainer):

```sh
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml logs -f localhost_forward_proxy
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml stop localhost_forward_proxy
docker compose --project-directory .devcontainer -f .devcontainer/compose.yaml start localhost_forward_proxy
```

# Domain context — SSH agent in the devcontainer

Private keys stay on the host. Before the container starts, `initializeCommand` runs `.devcontainer/scripts/shell/initializeCommand.sh` (VS Code, Cursor, and `devcontainer up`):

1. **`ensure-host-ssh-agent`** — selects or starts a host agent, loads default keys when possible (desktop session, 1Password, macOS Keychain, managed socket); may prompt once (TTY / Keychain UI / askpass); writes `.devcontainer/.selected-ssh-agent.env` with the chosen socket path
2. **`write-devcontainer-env`** — writes gitignored `.devcontainer/.env` (`DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, `HOST_SSH_AUTH_SOCK`, `HOST_WORKSPACE_DIR`) for Compose/Dockerfile bind mounts

Compose forwards the host agent at `/ssh-agent.sock` (from `HOST_SSH_AUTH_SOCK`) and mounts `known_hosts` read-only. `ensure-auth` (inside the container) reports whether identities are loaded; it does not unlock keys.

If the agent is empty after start, reopen in the container (re-runs initializeCommand) or use `gh auth login` (HTTPS). Before manual `docker compose up`, re-run `initializeCommand.sh` on the host so `.env` reflects current host paths (`.env` is workspace-writable from inside a running container).

When `initializeCommand` runs inside an outer devcontainer, `write-devcontainer-env` resolves Docker-host bind paths from trusted `../.devcontainer/.env` (requires `../.devcontainer/compose.yaml`).

On WSLg, the managed agent socket path may differ between manual compose and the normal initialize flow — see [WSLg ssh-agent socket path](wslg_ssh_agent_socket_path.md).

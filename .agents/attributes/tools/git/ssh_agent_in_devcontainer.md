# Domain context — SSH agent in the devcontainer

Private keys stay on the host. `initializeCommand` runs `.devcontainer/scripts/shell/initializeCommand.sh` before the container starts (VS Code, Cursor, and `devcontainer up`). That script calls:

- `ensure-host-ssh-agent`: prefers an already-unlocked host agent (desktop session, 1Password, prior Keychain load); may prompt once to unlock default keys (TTY / Keychain UI / askpass)
- `write-devcontainer-env`: writes `.devcontainer/.env` (`DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, `HOST_SSH_AUTH_SOCK`, `HOST_WORKSPACE_DIR`)

Compose mounts the host agent at `/ssh-agent.sock` and `known_hosts` read-only. `ensure-auth` (inside the container) only reports whether identities are loaded. If the agent is empty, reopen in the container (re-runs initializeCommand) or use `gh auth login` (HTTPS).

On WSLg, the managed agent socket path may differ between manual compose and the normal initialize flow — see [WSLg ssh-agent socket path](wslg_ssh_agent_socket_path.md).

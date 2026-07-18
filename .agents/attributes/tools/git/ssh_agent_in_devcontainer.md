# Domain context — SSH agent in the devcontainer

Private keys stay on the host. `initializeCommand` runs `.devcontainer/scripts/initialize/ensure-host-ssh-agent` before the container starts (VS Code, Cursor, and `devcontainer up`). That script:

- Writes `.devcontainer/.env` (`DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, `HOST_SSH_AUTH_SOCK`)
- Prefers an already-unlocked host agent (desktop session, 1Password, prior Keychain load)
- May prompt once to unlock default keys (TTY / Keychain UI / askpass)

Compose mounts the host agent at `/ssh-agent.sock` and `known_hosts` read-only. `ensure-auth` (inside the container) only reports whether identities are loaded. If the agent is empty, reopen in the container (re-runs initializeCommand) or use `gh auth login` (HTTPS).

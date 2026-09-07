# Domain context — SSH agent in the devcontainer

Private keys stay on the host. `initializeCommand` runs `.devcontainer/scripts/shell/initializeCommand.sh` before the container starts (VS Code, Cursor, and `devcontainer up`). That script calls:

- `ensure-host-ssh-agent`: prefers an already-unlocked host agent (desktop session, 1Password, prior Keychain load); may prompt once to unlock default keys (TTY / Keychain UI / askpass)
- `write-devcontainer-env`: writes `.devcontainer/.env` (`DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, `HOST_SSH_AUTH_SOCK`)

Compose mounts the host agent at `/ssh-agent.sock` and `known_hosts` read-only. `ensure-auth` (inside the container) only reports whether identities are loaded. If the agent is empty, reopen in the container (re-runs initializeCommand) or use `gh auth login` (HTTPS).

### WSLg socket path

On WSLg, `XDG_RUNTIME_DIR` is often `/mnt/wslg/runtime-dir`. Two paths can appear for the managed agent socket:

| When | Typical path |
|------|----------------|
| Manual `docker compose` **before** `.env` exists (compose default) | `$XDG_RUNTIME_DIR/super_projects-ssh-agent.sock` (e.g. `/mnt/wslg/runtime-dir/...`) |
| After `initializeCommand` (`.env` / normal devcontainer flow) | `$HOME/.cache/super_projects-ssh-agent.sock` |

`ensure-host-ssh-agent` deliberately uses `~/.cache/...` on WSLg because WSLg’s runtime dir can leave a **directory** at the socket path, which breaks `ssh-agent`. The compose default without `.env` still uses `$XDG_RUNTIME_DIR` so manual `docker compose down` / `ps` do not fail (PR #18); once initialize runs, `.env` records the `~/.cache` path and that is what devcontainer uses. Both paths are valid; no action needed unless you hand-edit `.env`.

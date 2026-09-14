# Domain context — WSLg ssh-agent socket path

When **WSLg** sets `XDG_RUNTIME_DIR` under `/mnt/wslg/` (often `/mnt/wslg/runtime-dir`), the **managed** agent socket path used by `ensure-host-ssh-agent` can differ from the compose fallback when `.devcontainer/.env` is missing. Forks rename `super_projects-ssh-agent.sock` per fork guidelines.

| When | Typical managed-socket path |
|------|----------------------------|
| Manual `docker compose` before `.env` exists (compose `${HOST_SSH_AUTH_SOCK:-...}` default) | `$XDG_RUNTIME_DIR/super_projects-ssh-agent.sock` |
| After `initializeCommand` when the managed socket is selected | `$HOME/.cache/super_projects-ssh-agent.sock` |

`ensure-host-ssh-agent` uses `~/.cache/...` on WSLg because the runtime-dir path can be occupied by a **directory**, which prevents `ssh-agent` from binding a socket. Compose keeps the `$XDG_RUNTIME_DIR` default so manual `docker compose down`, `ps`, and `config` work before initialize has run.

After initialize, `write-devcontainer-env` copies the selected socket from `.devcontainer/.selected-ssh-agent.env` into `HOST_SSH_AUTH_SOCK` in `.env`; devcontainer then bind-mounts that path to `/ssh-agent.sock`.

If an already-unlocked agent is reused instead (desktop `SSH_AUTH_SOCK`, 1Password, or a prior session), `.env` records that agent’s path and the table above may not apply.

When the two managed paths differ on WSLg, treat that as expected. If SSH fails after manual compose without re-running initialize, run `.devcontainer/scripts/shell/initializeCommand.sh` on the host before starting the container again.

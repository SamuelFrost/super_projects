# Domain context — WSLg ssh-agent socket path

When developing on **WSLg** (`XDG_RUNTIME_DIR` often `/mnt/wslg/runtime-dir`), two different host paths can appear for the managed agent socket (`super_projects-ssh-agent.sock` in a fork; rename per fork guidelines):

| When | Typical path |
|------|----------------|
| Manual `docker compose` before `.devcontainer/.env` exists (compose default) | `$XDG_RUNTIME_DIR/super_projects-ssh-agent.sock` |
| After `initializeCommand` (normal VS Code / Cursor / `devcontainer up` flow) | `$HOME/.cache/super_projects-ssh-agent.sock` |

`ensure-host-ssh-agent` uses `~/.cache/...` on WSLg because WSLg’s runtime directory can leave a **directory** at the socket path, which breaks `ssh-agent`. The compose default without `.env` still uses `$XDG_RUNTIME_DIR` so manual `docker compose down` / `ps` succeed when `.env` has not been generated yet. Once initialize runs, `.env` records the `~/.cache` path and devcontainer uses that for the bind mount.

When both paths differ, treat this as expected on WSLg — no action needed unless `.env` was hand-edited. If SSH fails after a manual compose command, re-run `scripts/shell/initializeCommand.sh` on the host before starting the container again.

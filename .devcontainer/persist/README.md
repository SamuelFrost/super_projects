# Persisted tool state (named volumes)

Durable tool state lives in **named Docker volumes** (good I/O on macOS). Each volume is mounted twice: at the conventional path under `/home/developer`, and again here as a shortcut so you can browse everything from one tree **inside the container**.

Volume names are prefixed with `${SUPER_PROJECTS_NAME}` (Compose `name:`, default `super_projects`). Because these volumes hold credentials and other tool state, set `${SUPER_PROJECTS_NAME}` in `.devcontainer/.env.namespace_override` so two clones on the same machine don't silently share them — see "Forking for your company" in the root README.

On the **host**, these shortcut directories are mount points and often look empty. Inspect data with:

```sh
devcontainer exec --workspace-folder . -- ls -la /${SUPER_PROJECTS_WORKDIR}/.devcontainer/persist
```

| Shortcut | Docker volume | Home path | Purpose |
|----------|---------------|-----------|---------|
| `gemini/` | `${SUPER_PROJECTS_NAME}_gemini-data` | `~/.gemini` | Gemini CLI sessions/config |
| `gh/` | `${SUPER_PROJECTS_NAME}_gh-data` | `~/.config/gh` | GitHub CLI auth |
| `git/` | `${SUPER_PROJECTS_NAME}_git-config` | `~/.config/git` | Git XDG config (`config`, etc.) |
| `mise/` | `${SUPER_PROJECTS_NAME}_mise-data` | `~/.local/share/mise` | mise downloads and tool installs |
| `chrome/` | `${SUPER_PROJECTS_NAME}_chrome-devtools-mcp-profile` | `~/chrome-profile` | Chrome profile (logins, cookies, extensions) |
| `cursor/` | `${SUPER_PROJECTS_NAME}_cursor-data` | `~/.cursor` | Cursor CLI auth/session state, agent transcripts, MCP config, skills |

## Reset a store

Stop the container, then remove the volume:

```sh
docker volume rm ${SUPER_PROJECTS_NAME}_gemini-data
docker volume rm ${SUPER_PROJECTS_NAME}_gh-data
docker volume rm ${SUPER_PROJECTS_NAME}_git-config
docker volume rm ${SUPER_PROJECTS_NAME}_mise-data
docker volume rm ${SUPER_PROJECTS_NAME}_chrome-devtools-mcp-profile
docker volume rm ${SUPER_PROJECTS_NAME}_cursor-data
```

## First-time enable (cursor)

When `cursor-data` is added to an existing devcontainer, Docker creates an **empty** named volume on rebuild. Copy current state to the workspace bind mount first, then restore after rebuild:

```sh
# 1. Before rebuild (inside the running container):
cp -a ~/.cursor /${SUPER_PROJECTS_WORKDIR}/.devcontainer/cursor-migration-backup

# 2. Rebuild/recreate the devcontainer, then restore:
cp -a /${SUPER_PROJECTS_WORKDIR}/.devcontainer/cursor-migration-backup/. ~/.cursor/
rm -rf /${SUPER_PROJECTS_WORKDIR}/.devcontainer/cursor-migration-backup
```

The backup directory is gitignored but lives on the host workspace disk and includes Cursor CLI auth/session state — remove it after a successful restore; do not leave it in the repo directory.

After that, `~/.cursor` (agent-transcripts, CLI chats, MCP config, skills) survives container rebuilds. IDE sidebar chat index on the Cursor host app is separate; this volume covers container-side state only.

## SSH (host agent — keys not in the container)

Private keys are **not** mounted. Compose forwards a host `ssh-agent` socket to `/ssh-agent.sock`.

`initializeCommand` runs `.devcontainer/scripts/shell/initializeCommand.sh` (which calls `ensure-host-ssh-agent` and `write-devcontainer-env`) to write `.devcontainer/.env` (bind-mount vars plus `SUPER_PROJECTS_NAME` and `SUPER_PROJECTS_WORKDIR` from `.env.namespace_override`). Key unlock may prompt once (TTY, Keychain, or askpass). Prefer macOS `UseKeychain yes`, 1Password’s SSH agent, or `gh auth login` (HTTPS) to avoid repeated prompts. Manual Compose must use `--project-directory .devcontainer`.

`known_hosts` is bind-mounted read-only from the host.

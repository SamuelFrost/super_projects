# Persisted tool state (named volumes)

Durable tool state lives in **named Docker volumes** (good I/O on macOS). Each volume is mounted twice: at the conventional path under `/home/developer`, and again here as a shortcut so you can browse everything from one tree **inside the container**.

Volume names are prefixed with the Docker Compose project name (`name:` in `compose.yaml`, `super_projects` by default). Because these volumes hold credentials and other tool state, forks must rename the project so two forks on the same machine don't silently share them — see "Forking for your company" in the root README.

On the **host**, these shortcut directories are mount points and often look empty. Inspect data with:

```sh
devcontainer exec --workspace-folder . -- ls -la /workspaces/.devcontainer/persist
```

| Shortcut | Docker volume | Home path | Purpose |
|----------|---------------|-----------|---------|
| `gemini/` | `super_projects_gemini-data` | `~/.gemini` | Gemini CLI sessions/config |
| `gh/` | `super_projects_gh-data` | `~/.config/gh` | GitHub CLI auth |
| `git/` | `super_projects_git-config` | `~/.config/git` | Git XDG config (`config`, etc.) |
| `mise/` | `super_projects_mise-data` | `~/.local/share/mise` | mise downloads and tool installs |
| `chrome/` | `super_projects_chrome-devtools-mcp-profile` | `~/chrome-profile` | Chrome profile (logins, cookies, extensions) |
| `cursor/` | `super_projects_cursor-data` | `~/.cursor` | Agent transcripts, CLI sessions, MCP config, skills |

## Reset a store

Stop the container, then remove the volume:

```sh
docker volume rm super_projects_gemini-data
docker volume rm super_projects_gh-data
docker volume rm super_projects_git-config
docker volume rm super_projects_mise-data
docker volume rm super_projects_chrome-devtools-mcp-profile
docker volume rm super_projects_cursor-data
```

## First-time enable (cursor)

When `cursor-data` is added to an existing devcontainer, Docker creates an **empty** named volume on rebuild. Copy current state to the workspace bind mount first, then restore after rebuild:

```sh
# 1. Before rebuild (inside the running container):
cp -a ~/.cursor /workspaces/.devcontainer/cursor-migration-backup

# 2. Rebuild/recreate the devcontainer, then restore:
cp -a /workspaces/.devcontainer/cursor-migration-backup/. ~/.cursor/
rm -rf /workspaces/.devcontainer/cursor-migration-backup
```

After that, `~/.cursor` (agent-transcripts, CLI chats, MCP config, skills) survives container rebuilds. IDE sidebar chat index on the Cursor host app is separate; this volume covers container-side state only.

## SSH (host agent — keys not in the container)

Private keys are **not** mounted. Compose forwards a host `ssh-agent` socket to `/ssh-agent.sock`.

`initializeCommand` runs `scripts/shell/initializeCommand.sh` (which calls `ensure-host-ssh-agent` and `write-devcontainer-env`) to write `.devcontainer/.env` (`DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, `HOST_SSH_AUTH_SOCK`, `HOST_WORKSPACE_DIR`). Key unlock may prompt once (TTY, Keychain, or askpass). Prefer macOS `UseKeychain yes`, 1Password’s SSH agent, or `gh auth login` (HTTPS) to avoid repeated prompts.

`known_hosts` is bind-mounted read-only from the host.

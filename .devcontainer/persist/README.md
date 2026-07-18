# Persisted tool state (named volumes)

Durable tool state lives in **named Docker volumes** (good I/O on macOS). Each volume is mounted twice: at the conventional path under `/home/developer`, and again here as a shortcut so you can browse everything from one tree **inside the container**.

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

## Reset a store

Stop the container, then remove the volume:

```sh
docker volume rm super_projects_gemini-data
docker volume rm super_projects_gh-data
docker volume rm super_projects_git-config
docker volume rm super_projects_mise-data
docker volume rm super_projects_chrome-devtools-mcp-profile
```

## SSH (not a project volume)

`~/.ssh` is bind-mounted from the **host** home directory (`HOST_HOME_DIR` / `$HOME`), not a Docker volume and not stored under this tree. That keeps the same keys available outside the container; it also means host private keys are visible inside the container if it is compromised.

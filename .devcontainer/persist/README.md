# Persisted tool state (named volumes)

Docker-managed named volumes preserve tool state across container recreation on macOS Docker Desktop, WSL2, and Linux. Devcontainer tool-state volumes have shortcuts under `.devcontainer/persist/` for browsing **inside the container**. These shortcuts are not host bind mounts and can look empty on the host.

Volume names are prefixed by the Compose project name. Set a distinct name in `docker_compose_configuration_customizations/naming/compose.naming.override.yaml` for each clone so separate environments do not share credentials and histories. Changing the project name does not move existing data.

| Shortcut | Docker volume | Container mount | Contents |
|----------|---------------|-----------------|----------|
| `codex/` | `<name>_codex-state` | `~/.codex` | Codex login, settings, and sessions |
| `chatgpt/` | `<name>_chatgpt-state` | `~/.config/Codex` | ChatGPT desktop profile |
| `claude-code/` | `<name>_claude-code-state` | `~/.claude` | Claude Code login, settings, and sessions |
| `claude-desktop/` | `<name>_claude-desktop-state` | `~/.config/Claude` | Claude Desktop profile |
| `cursor/` | `<name>_cursor-data` | `~/.cursor` | Cursor Agent state and sessions |
| `cursor-config/` | `<name>_cursor-config-state` | `~/.config/cursor` | Cursor Agent Linux login and configuration |
| `cursor-desktop/` | `<name>_cursor-desktop-state` | `~/.config/Cursor` | Cursor IDE profile |
| `cursor-server/` | `<name>_cursor-server-state` | `~/.cursor-server` | Cursor remote server, extensions, settings, and remote workspace state |
| `vscode-profile/` | `<name>_vscode-profile-state` | `~/.config/Code` | VS Code settings, workspace state, chat history, and account profile |
| `vscode-extensions/` | `<name>_vscode-extensions-state` | `~/.vscode` | VS Code installed desktop extensions and CLI state |
| `vscode-server/` | `<name>_vscode-server-state` | `~/.vscode-server` | VS Code remote server, extensions, settings, and remote workspace state |
| `gemini/` | `<name>_gemini-data` | `~/.gemini` | Gemini CLI login, sessions, settings, and caches |
| `desktop-keyrings/` | `<name>_desktop-keyrings` | `~/.local/share/keyrings` | Secret Service credentials shared by native GUI apps |
| `chrome/` | `<name>_chrome-devtools-mcp-profile` | `~/chrome-profile` | Browser logins, profiles, extensions; Gemini web app; separate `pwa/` profile |
| `gh/` | `<name>_gh-data` | `~/.config/gh` | GitHub CLI authentication |
| `git/` | `<name>_git-config` | `~/.config/git` | Git configuration |
| `mise/` | `<name>_mise-data` | `~/.local/share/mise` | Runtime/tool installations and caches |
| No devcontainer shortcut | `<name>_local-llm` | `/root/.ollama` in `local-llm` | Ollama downloaded models and model metadata |

## Application storage

Each application uses its normal directory, mounted directly from a named Docker
volume. Application binaries remain in the image outside these volumes. CLI and
desktop applications retain separate profiles and may require separate logins.

`CLAUDE_CONFIG_DIR=/home/developer/.claude` keeps global `.claude.json` inside the persisted `~/.claude` directory as well. GNOME Keyring starts in the XFCE session. Follow its normal prompt to create or unlock the login keyring when an application needs it; no keyring password is stored in the image.

Gemini's GUI uses the shared Chrome profile rather than a separate native desktop store. Host IDE installations have their own profiles. The local `lllm` database and transcripts remain on the workspace bind mount under `.devcontainer/lllm/.adk/` and `.devcontainer/lllm/.local_only/`; Ollama models and metadata persist in the separate `local-llm` service’s volume across service recreation and image rebuilds. Changing `GEMMA_MODEL` retains previously downloaded models; use `ollama rm` in that service to remove models no longer needed.

Changing `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, `CURSOR_CONFIG_DIR`, `GEMINI_CLI_HOME`, or XDG paths requires corresponding storage changes. Environment-provided API keys must still be supplied after rebuilding. Apps can expire logins or prune old sessions according to their retention settings. Volumes persist on the selected Docker daemon; they do not automatically synchronize between machines.

## Host and desktop IDE boundaries

Cursor and VS Code desktop launchers open `/workspaces`. Project `.vscode/`,
`.cursor/`, and `.code-workspace` files are shared through the workspace bind mount.
Open the same folder or saved workspace consistently: each has its own IDE
workspace settings and history.

Host-connected IDEs and desktop IDEs keep separate profiles and chat histories.
The remote server volumes preserve container-side servers, remote extensions,
and workspace state; they do not synchronize host profiles with desktop profiles.
Only the preference files described below are shared from the host.

## Host user settings

The host `initializeCommand` automatically detects existing stable VS Code and
Cursor user settings and key mappings and adds a read-only bind for each existing
`settings.json` and `keybindings.json` file at
its corresponding desktop profile path. The host is authoritative for user
preferences; project and `.code-workspace` settings remain editable and shared
through the workspace bind mount.

| Initialization environment | Settings discovery |
| --- | --- |
| macOS | `~/Library/Application Support/{Code,Cursor}/User/settings.json` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/{Code,Cursor}/User/settings.json` |
| Windows through WSL | Ask PowerShell for the current Windows user's AppData, convert it with `wslpath`, and use existing Windows profiles; otherwise fall back to native Linux profiles. |
| Windows POSIX shell (MSYS/Git Bash/Cygwin) | Use `APPDATA`, converting with `cygpath` when available. The existing devcontainer host hooks still require a POSIX shell. |
| Nested container or remote Docker endpoint | Keep the container's persisted preferences; do not guess the original host's paths. |

The generated `host_ide_settings/compose.host-ide-settings.yaml` is ignored by Git.
Missing preference files leave the container’s persisted preferences in use.

For custom or portable profiles, the optional host environment variables
`SUPER_PROJECTS_VSCODE_USER_SETTINGS` and `SUPER_PROJECTS_CURSOR_USER_SETTINGS`
select explicit absolute settings-file paths. Key mappings are discovered beside
that file; `SUPER_PROJECTS_VSCODE_USER_KEYBINDINGS` and
`SUPER_PROJECTS_CURSOR_USER_KEYBINDINGS` can select separate absolute keybindings
files. If only a keybindings override is supplied, settings are discovered beside
it. Set `SUPER_PROJECTS_HOST_IDE_SETTINGS=disabled`
to keep independent container user preferences. These variables take effect
during host initialization.

Edit user preferences through the host IDE; container user settings are read-only
while shared. A host editor that replaces the file atomically can leave an
existing file mount on the old inode; recreate the container to refresh it.
Machine-specific absolute paths are not rewritten, and host extension binaries,
credentials, profiles, and chat history are not imported. Key mappings are shared
as written: macOS modifier keys and OS-specific `when` conditions are not translated. Use project
or workspace settings for container-specific overrides. Existing privacy policies
and desktop telemetry flags still apply.

## VS Code extensions

VS Code includes Copilot Chat. Fresh `vscode-extensions-state` volumes inherit
extensions installed in the image, including Codex. Existing volumes retain their
installed extensions across rebuilds and do not automatically receive extensions
added to a newer image. Provider extensions may also use CLI storage such as
`~/.codex`.

See [privacy controls](../privacy/README.md) for telemetry policies and provider
account training settings.

## Reset a store

Deleting an application volume deletes the state stored in that directory. Ordinary `docker compose down` preserves volumes; `down --volumes`, volume pruning, or explicit volume removal can delete them. Stop the containers before intentionally removing a store, for example:

```sh
docker volume rm <name>_codex-state
```

Sources: [Docker volumes](https://docs.docker.com/engine/storage/volumes/), [Gemini sessions](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md), [Codex authentication](https://learn.chatgpt.com/docs/auth), [Claude configuration](https://code.claude.com/docs/en/settings), [Cursor installation](https://cursor.com/docs/get-started/quickstart), [ChatGPT Linux installation](https://learn.chatgpt.com/docs/linux/linux-app), [Claude Desktop installation](https://support.claude.com/en/articles/10065433-install-claude-desktop).

## SSH (host agent — keys not in the container)

Private keys are **not** mounted. Compose forwards a host `ssh-agent` socket to `/ssh-agent.sock`.

`initializeCommand` runs `.devcontainer/scripts/shell/initializeCommand.sh` (which calls `write-compose-ssh-agent-socket`, `write-compose-user-ids`, `write-compose-project-directory`, and `write-compose-ssh-known-hosts`) to write those Compose files. The name comes from `compose.naming.yaml`, replaced by `compose.naming.override.yaml` when that file exists. Key unlock may prompt once (TTY, Keychain, or askpass). Prefer macOS `UseKeychain yes`, 1Password’s SSH agent, or `gh auth login` (HTTPS) to avoid repeated prompts. To run Compose directly, use `./not_devcontainer <command>` (for example `./not_devcontainer down`).

`known_hosts` is bind-mounted read-only from the host.

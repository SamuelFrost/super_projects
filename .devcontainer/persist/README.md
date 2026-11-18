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
| `vscode-extensions/` | `<name>_vscode-extensions-state` | `~/.vscode` | VS Code desktop CLI state and previously installed local extensions |
| `vscode-server/` | `<name>_vscode-server-state` | `~/.vscode-server` | VS Code remote server, extensions, settings, and remote workspace state |
| `gemini/` | `<name>_gemini-data` | `~/.gemini` | Gemini CLI login, sessions, settings, and caches |
| `chrome/` | `<name>_chrome-devtools-mcp-profile` | `~/chrome-profile` | Browser logins, profiles, extensions; Gemini web app; separate `pwa/` profile |
| `gh/` | `<name>_gh-data` | `~/.config/gh` | GitHub CLI authentication |
| `git/` | `<name>_git-config` | `~/.config/git` | Git configuration |
| `mise/` | `<name>_mise-data` | `~/.local/share/mise` | Runtime/tool installations and caches |
| No devcontainer shortcut | `<name>_local-llm` | `/root/.ollama` in `local-llm` | Ollama downloaded models and model metadata |

## Application storage

Each application uses its normal directory, mounted directly from a named Docker
volume. Image-installed application binaries remain outside these volumes.
Downloaded remote IDE servers, extensions, and mise-managed tools persist in
their respective volumes. CLI and desktop applications retain separate profiles
and may require separate logins.

`CLAUDE_CONFIG_DIR=/home/developer/.claude` keeps global `.claude.json` inside the persisted `~/.claude` directory as well.

Opening a terminal and container startup diagnostics do not access GitHub credentials; use `gh auth status` explicitly to check them.

Gemini's GUI uses the shared Chrome profile rather than a separate native desktop store. Host IDE installations have their own profiles. The local `lllm` database and transcripts remain on the workspace bind mount under `.devcontainer/lllm/.adk/` and `.devcontainer/lllm/.local_only/`; Ollama models and metadata persist in the separate `local-llm` service’s volume across service recreation and image rebuilds. Changing `GEMMA_MODEL` retains previously downloaded models; use `ollama rm` in that service to remove models no longer needed.

Changing `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, `CURSOR_CONFIG_DIR`, `GEMINI_CLI_HOME`, or XDG paths requires corresponding storage changes. Environment-provided API keys must still be supplied after rebuilding. Apps can expire logins or prune old sessions according to their retention settings. Volumes persist on the selected Docker daemon; they do not automatically synchronize between machines.

## Login from the host browser

Run these commands in an interactive terminal **inside the container**, then open
the supplied authorization URL in your host browser. Complete sign-in there using
your existing browser session or password manager. The provider issues credentials
to the container application; your account password need not enter the container.

| Tool | Container login command | Host browser action |
| --- | --- | --- |
| Codex | `codex login --device-auth` | Open the URL and enter the one-time code. Device login must be enabled in your account or workspace settings. |
| Claude Code | `claude auth login` (or `/login` inside Claude) | Open the supplied URL and approve access. If shown an authorization code, paste it into Claude's terminal prompt. |
| Cursor CLI | `NO_OPEN_BROWSER=1 agent login` | Open the printed URL and approve access. |
| Gemini CLI | `NO_BROWSER=true gemini` | Select Google login and follow the manual URL/code prompts. |

The resulting login state uses the volumes listed above and survives rebuilds.
Applications refresh credentials according to provider behavior; expired or revoked
access can require another login. CLI login does not automatically sign in separate
desktop apps or websites. Their own login flows can require application-specific
callback handling.

Sources: [Codex authentication](https://learn.chatgpt.com/docs/auth),
[Claude Code authentication](https://code.claude.com/docs/en/authentication),
[Cursor CLI authentication](https://cursor.com/docs/cli/reference/authentication),
and [Gemini's manual authorization implementation](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/code_assist/oauth2.ts).

### Credential protection boundary

Host-browser authorization separates your account password from the container,
but access and refresh tokens are still reusable credentials stored inside it.
API-key authentication likewise supplies a reusable secret to the container.
Agents running as the same user can access application state, and access to the
host Docker socket can bypass container file permissions. Passwords entered into
the container's agent-controlled browser may also be observed during login.

Credential encryption and stronger isolation from agents are deferred work; this
setup does not provide a shared encrypted credential store. Keep original passwords
and SSH private keys on the host, using host SSH-agent forwarding for SSH. Host
disk encryption (FileVault, BitLocker, or Linux LUKS) can protect Docker storage
while offline when the volume containing that storage is encrypted; it does not
protect credentials from processes in a running, unlocked environment.

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

## Editor extensions

Dev Containers clients install the extensions listed in
[`devcontainer.json`](../devcontainer.json) during editor setup. Install or
update extensions through the host editor while connected to the container.
The browser desktop launchers for VS Code and Cursor read the corresponding
server's `extensions` directory through a read-only mount. Restart the
desktop editor to pick up changes if it's already open. Extensions that run
only in the host editor stay on the host.

Before the desktop starts, Compose prepares the persisted VS Code and Cursor
desktop profiles for the configured developer UID. This also repairs older
profiles created as root. Host settings and keybindings are mounted separately
and stay read-only.

Editor profiles and remote extension stores persist across rebuilds. The
browser desktop launchers use the server stores in place of any extensions
previously installed into the standalone desktop directories. The read-only
mount blocks writes through the desktop extension path. The development user
can also access the writable server volume and the Docker socket.

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

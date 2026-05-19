# super_projects

A containerized parent-directory environment for software development teams.

Fork this repository, place it where you would normally keep your projects directory, and open it in VS Code or Cursor to get a fully configured development container your whole team can share.

## What this is

`super_projects` is designed to sit **in place of** your projects parent directory. Rather than configuring each developer's machine individually, the dev environment (Docker, IDE settings, AI tooling) is codified here and shared via git.

Teams fork this repo and maintain their own version of the Docker image, devcontainer settings, and IDE extensions — so every developer gets an identical, reproducible environment.

## What's tracked in git

The `.gitignore` is configured to ignore everything **except** the files that define the development environment:

| Path | Purpose |
|------|---------|
| `.devcontainer/` | Dockerfile, compose, and devcontainer config |
| `.cursor/` | Cursor IDE rules, settings, and skills |
| `.claude/` | Claude project config |
| `.vscode/` | VS Code settings and extension recommendations |
| `README.md` | This file |
| `AGENTS.md` / `agents.md` | AI agent context for tools like Claude Code, Gemini CLI |

Individual project directories cloned inside here are **not tracked** by this repo.

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux)
- Atleast one of the following: 
  - [Dev Containers CLI](https://github.com/devcontainers/cli)
  - [VS Code](https://code.visualstudio.com/download) (with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers))
  - [Cursor](https://cursor.com/download) (with the Dev Containers extension)

Clone this repo where you keep your projects; you can make it the parent directory of all your projects, for a few select projects, or use it as a monorepo. It's recommended you fork this repo and keep your own version for your team.
```sh
git clone git@github.com:samuelfrost/super_projects.git
```

---

### Option A — CLI (no IDE required)

```sh
# Build and start (runs initializeCommand to generate .env, then builds + starts)
devcontainer up --remove-existing-container

# Open a shell inside the container
devcontainer exec bash

# Manually start/restart Chrome inside the container (auto-starts with the container)
devcontainer exec chrome

# Stop
docker compose -f .devcontainer/compose.yaml down
```

The VNC desktop and Chrome start automatically with the container — no extra steps needed.

---

### Option B — VS Code / Cursor

- **WSL users:** enable `dev.containers.executeInWSL` in your editor settings so SSH and UID mounts resolve correctly

1. Open the directory in [VS Code](https://code.visualstudio.com/download) (with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)) or [Cursor](https://cursor.com/download) (with the Dev Containers extension).
2. When prompted, click **Reopen in Container** (or run the _Dev Containers: Reopen in Container_ command).
3. The container builds once; subsequent opens are fast.

## Devcontainer details

The devcontainer is a standalone **Ubuntu 24.04** image defined entirely in `.devcontainer/Dockerfile`. It includes:

- `git`, `gh` (GitHub CLI), `openssh-client`
- Docker CLI + Compose + Buildx plugins (docker-outside-of-docker via socket mount)
- Node.js + npm
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (`gemini` command; free tier available)
- `ffmpeg`, `poppler-utils`, `procps`, and other common dev utilities
- Fully functioning desktop GUI (XFCE desktop + VNC + noVNC) at `http://localhost:6080/vnc.html`
- Google Chrome, launched with remote debugging on port 9223 (accessible from the desktop GUI and via MCP)
- `.cursor/mcp.json` wires up the official [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp) via `npx` — Cursor connects to Chrome through the forwarded port, no custom proxy needed
- Recommended extensions and settings for VS Code and Cursor
- TODO: Add mise for version management
- TODO: add rubylsp, stimulus-lsp, and herb-lsp for language servers
- TODO: fix file ownership issues with the devcontainer

The VNC/Chrome stack starts automatically when the container starts and can be restarted at any time by running `start-vnc` inside the container.

### Persisted data

| Volume | Container path | Purpose |
|--------|---------------|---------|
| `.devcontainer/gemini-data/` (bind) | `~/.gemini` | Gemini CLI sessions/config (gitignored) |
| `~/.bash_history` (host bind) | `~/.bash_history` | Shell history continuity |
| `~/.ssh` (host bind) | `~/.ssh` | SSH key forwarding |
| `super_projects_chrome-devtools-mcp-profile` (named volume) | `~/chrome-profile` | Chrome logins, cookies, extensions |

The Chrome profile is stored in a named Docker volume so it survives container rebuilds. It is only lost if you explicitly remove the volume:
```sh
docker volume rm super_projects_chrome-devtools-mcp-profile
```

### Enabling Claude Code CLI

The Claude Code CLI setup is included but commented out in the Dockerfile. To enable it, uncomment the relevant lines and rebuild the container.

## Customising for your team

- **Add tools:** edit `.devcontainer/Dockerfile` and rebuild.
- **Add extensions:** add extension IDs to the `customizations.vscode.extensions` array in `.devcontainer/devcontainer.json`.
- **Add environment variables:** use `containerEnv` in `devcontainer.json` for variables that should always be set inside the container.
- **Project-specific services** (databases, caches, etc.): add services to `.devcontainer/compose.yaml`.

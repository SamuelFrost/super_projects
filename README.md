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
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), or [Cursor](https://cursor.sh/)
- **WSL users:** enable `dev.containers.executeInWSL` in your editor settings so SSH and UID mounts resolve correctly

### Steps

1. Fork this repo and clone it where you keep your projects:
   ```sh
   git clone git@github.com:<your-org>/super_projects.git ~/projects
   ```
2. Open the directory in VS Code or Cursor.
3. When prompted, click **Reopen in Container** (or run the _Dev Containers: Reopen in Container_ command).
4. The container builds once; subsequent opens are fast.

## Devcontainer details

The devcontainer is a standalone **Ubuntu 24.04** image defined entirely in `.devcontainer/Dockerfile`. It includes:

- `git`, `gh` (GitHub CLI), `openssh-client`
- Docker CLI + Compose + Buildx plugins (docker-outside-of-docker via socket mount)
- Node.js + npm
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (`gemini` command; free tier available)
- `ffmpeg`, `poppler-utils`, `procps`, and other common dev utilities

### Persisted data

| Volume | Container path | Purpose |
|--------|---------------|---------|
| `.devcontainer/gemini-data/` | `~/.gemini` | Gemini CLI sessions/config (gitignored) |
| `~/.bash_history` (host) | `~/.bash_history` | Shell history continuity |
| `~/.ssh` (host) | `~/.ssh` | SSH key forwarding |

### Enabling Claude Code CLI

The Claude Code CLI setup is included but commented out in the Dockerfile. To enable it, uncomment the relevant lines and rebuild the container.

## Customising for your team

- **Add tools:** edit `.devcontainer/Dockerfile` and rebuild.
- **Add extensions:** add extension IDs to the `customizations.vscode.extensions` array in `.devcontainer/devcontainer.json`.
- **Add environment variables:** use `containerEnv` in `devcontainer.json` for variables that should always be set inside the container.
- **Project-specific services** (databases, caches, etc.): add services to `.devcontainer/compose.yaml`.

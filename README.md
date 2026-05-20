# super_projects

A containerized parent-directory environment for software development teams.

Fork this repository, place it where you would normally keep your projects directory, and open it in VS Code or Cursor to get a fully configured development container your whole team can share.

## What this is

`super_projects` is designed to be your projects' parent directory. Rather than configuring each developer's machine individually, the dev environment (Docker, IDE settings, AI tooling) is codified here and shared via git.

Teams fork this repo and maintain their own version of the Docker image, devcontainer settings, and IDE extensions — so every developer gets an identical, reproducible environment.

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
- `.cursor/mcp.json` wires up the official [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp) via `npx` — Cursor connects to Chrome through the forwarded port.
- [mise](https://mise.jdx.dev) — universal version manager for Ruby, Node, Python, Go, Java, and more
- Recommended extensions and settings for VS Code and Cursor
- TODO: add ruby-lsp, stimulus-lsp, and herb-lsp for language servers

The VNC/Chrome stack starts automatically when the container starts and can be restarted at any time by running `start-vnc` inside the container.

### Persisted data

| Volume | Container path | Purpose |
|--------|---------------|---------|
| `.devcontainer/gemini-data/` (bind) | `~/.gemini` | Gemini CLI sessions/config (gitignored) |
| `~/.bash_history` (host bind) | `~/.bash_history` | Shell history continuity |
| `~/.ssh` (host bind) | `~/.ssh` | SSH key forwarding |
| `super_projects_chrome-devtools-mcp-profile` (named volume) | `~/chrome-profile` | Chrome logins, cookies, extensions |
| `super_projects_mise-data` (named volume) | `~/.local/share/mise` | mise downloads and tool installs |

The Chrome profile is stored in a named Docker volume so it survives container rebuilds. It is only lost if you explicitly remove the volume:
```sh
docker volume rm super_projects_chrome-devtools-mcp-profile
```

### Tool version management (mise)

`mise` is pre-installed and activated in every shell. Configure the tools your project needs by editing `.mise.toml` or including a `mise.toml` or `.tool-versions` file in the a project's directory see [mise documentation](https://mise.jdx.dev/getting-started.html) for more details.

Tools defined in the top level directory `.mise.toml` are installed automatically when the container starts (`mise install` in `compose.yaml`). Note: downloads and installs are stored in the `mise-data` Docker volume, so they will persist across container rebuilds unless you explicitly remove the volume with `docker volume rm super_projects_mise-data`.

To install tools from mise in a particular project directory run `mise install` in the project directory.

### Enabling Claude Code CLI

The Claude Code CLI setup is included but commented out in the Dockerfile. To enable it, uncomment the relevant lines and rebuild the container.

## Customising for your team

- **Add/modify tools:** edit `.devcontainer/Dockerfile` and rebuild.
- **Add/modify extensions:** add extension IDs to the `customizations.vscode.extensions` array in `.devcontainer/devcontainer.json`.
- **Add/modify environment variables:** use `containerEnv` in `devcontainer.json` for variables that should always be set inside the container.
- **Project-specific services** take advantage of the GUI and add emulators / browsers / other gui tools to the dockerfile build.

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

## Simple example project: To create a new rails project monorepo
<!-- note: Using this as a monorepo is a recommended pattern of this (if you plan to use it as a monorepo, you would want to fork and rename the repo, and remove the git ignores in this case), if you want to instead use it as a parent directory for this example, simply create the subdirectory and run the command and put the docker compose file inside it as desired. -->

```bash
docker run --rm --volume ${LOCAL_WORKSPACE_FOLDER:-.}:/app --workdir /app -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) ruby:latest bash -c 'gem install rails && rails new sample_app_1 --database=postgresql && chown -R $HOST_UID:$HOST_GID sample_app_1'
```
For best results, set up a docker-compose.yaml file to run postgres and the sample app in the same network so they can communicate with each other.

Example docker-compose.yaml file (place in the parent directory of the sample app, if following the above command, it will be directory of this repo or where you executed the command):
```yaml
name: super_projects_samples

services:
  sample_app_1:
    build:
      context: ./sample_app_1
      dockerfile: Dockerfile
    environment:
      - RAILS_ENV=development
      - SECRET_KEY_BASE=secret
      - DATABASE_URL=postgres://postgres:password@postgres:5432/sample_app_1_development
    ports:
      - "3000:80"
      # available on the host machine at http://localhost:3000
      # available within the container at http://sample_app_1 (note, you will need to add `config.hosts << "sample_app_1"` to config/environments/development.rb to access it from the chrome service inside the devcontainer)
    volumes:
      - ${LOCAL_WORKSPACE_FOLDER:-.}/sample_app_1:/rails
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - super_projects_default

  postgres:
    image: postgres:18.3
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: sample_app_1_development
    volumes:
      - sample_app_1_postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - super_projects_default

networks:
  super_projects_default:
    external: true

volumes:
  sample_app_1_postgres_data:
    external: false
    name: sample_app_1_postgres_data
```

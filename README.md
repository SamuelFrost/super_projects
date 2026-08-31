# super_projects

A containerized parent-directory environment for software development teams.

Fork this repository for your company, place your fork where you would normally keep your projects directory, and open it in VS Code or Cursor to get a fully configured development container your whole team can share.

## What this is

`super_projects` is designed to be your projects' parent directory. Rather than configuring each developer's machine individually, the dev environment (Docker, IDE settings, AI tooling) is codified here and shared via git.

It is a template meant to be forked once per company (or team), customized, and shared across the organization:

1. **Fork** this repo for your company.
2. **Rename** the container and related identifiers immediately — see [Forking for your company](#forking-for-your-company).
3. **Customize** the agent setups and tools to match your company's needs.
4. Developers clone the company fork where they keep their projects; individual project repositories live inside it as untracked subdirectories.

Each company maintains its own version of the Docker image, devcontainer settings, agent setups, and IDE extensions — so every developer gets an identical, reproducible environment. Using the repo as a monorepo (tracking project code directly in it) is no longer a recommended pattern; keep projects as separate repositories cloned inside your fork.

## Forking for your company

The intended way to use this project is one fork per company (or team). Your fork becomes your organization's shared development environment: customize it, commit the changes, and every developer gets them on the next pull and container rebuild.

### 1. Rename the container (do this first)

The Docker Compose project name — `name: "super_projects"` in `.devcontainer/compose.yaml` — determines the container name (`super_projects-devcontainer-1`), the Docker network name, and the prefix of every named volume. If your fork keeps the default name, it will collide with any other fork or copy of this project on the same machine, and Docker will silently **share the named volumes** between them. With the current setup that is usually not a big deal, but those volumes hold GitHub CLI auth tokens, the Chrome profile (logins and cookies), and git config — so a name collision can leak state and credentials between unrelated projects. Rename as soon as you fork, before anyone starts the container.

Replace `super_projects` with your company's project name (for example `acme_projects`) everywhere outside `LICENSE`:

```sh
git grep -l super_projects -- ':!LICENSE' | xargs sed -i 's/super_projects/acme_projects/g'
# macOS: use sed -i '' 's/super_projects/acme_projects/g'
```

Review the diff before committing (and revert any replacements in attribution or license text that should keep referring to the original project). The name appears in:

- `.devcontainer/compose.yaml` — compose project `name` (drives the container and volume names), `hostname`, and the `super_projects_default` network
- `.devcontainer/devcontainer.json` — devcontainer `name`
- `.cursor/mcp.json`, `.vscode/mcp.json`, `.mcp.json`, `.gemini/settings.json`, `.codex/config.toml` — the container name (`super_projects-devcontainer-1`) that MCP servers exec into
- `.devcontainer/scripts/initialize/ensure-host-ssh-agent` — the host ssh-agent socket filename
- `.devcontainer/scripts/dockerfile/print-cursor-worker-hint` — the suggested Cursor worker name
- `README.md` and `.devcontainer/persist/README.md` — volume names in documentation

If a container was already started under the old name, remove it first with `docker compose -f .devcontainer/compose.yaml down` (add `-v` to also remove the old volumes).

### 2. Customize the agent setups

Adapt the AI agent configuration to your company's workflows:

- Shared agent profiles and reusable behavior attributes live under `.agents/` — see [`.agents/agent_profiles/README.md`](.agents/agent_profiles/README.md). Each developer copies a profile to the untracked root `agents.md`; keep the shared templates in your fork up to date with your team's conventions.
- MCP server wiring lives in `.cursor/mcp.json`, `.vscode/mcp.json`, `.mcp.json`, `.gemini/settings.json`, and `.codex/config.toml` — add the servers your company uses and remove the ones it doesn't.

### 3. Add or remove tools

Match the toolset to your company's stack (details in [Customising for your team](#customising-for-your-team)):

- Language runtimes and versions: `.mise.toml`.
- System packages and CLIs: `.devcontainer/Dockerfile`.
- IDE extensions: `customizations.vscode.extensions` in `.devcontainer/devcontainer.json`.
- **Company-internal tools:** prefer installing them via Docker — bake them into `.devcontainer/Dockerfile`, or run them as additional services in `.devcontainer/compose.yaml` — so every developer gets them automatically instead of following manual setup steps.

Commit and push these changes to your fork, then have your team clone it and follow [Getting started](#getting-started).

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux)
- Atleast one of the following: 
  - [Dev Containers CLI](https://github.com/devcontainers/cli)
  - [VS Code](https://code.visualstudio.com/download) (with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers))
  - [Cursor](https://cursor.com/download) (with the Dev Containers extension)

Fork this repo for your company and rename it first (see [Forking for your company](#forking-for-your-company)), then clone your fork where you keep your projects — it can be the parent directory of all your projects or just a few select ones.
```sh
git clone git@github.com:<your-company>/<your-fork>.git
```

---

### Option A — CLI (no IDE required)

```sh
# Build and start (runs initializeCommand → ensure-host-ssh-agent to write .env, then builds + starts)
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

### SSH setup (passphrase-protected keys)

Private keys stay on the host; the container only gets a forwarded `ssh-agent` socket.

Unlocking happens automatically in **`initializeCommand`** (`ensure-host-ssh-agent`) before the container starts — the same hook used by **VS Code**, **Cursor** (“Reopen in Container”), and **`devcontainer up`**. That script also writes `.devcontainer/.env` with `DEVELOPER_UID`, `DOCKER_GID`, `HOST_HOME_DIR`, and `HOST_SSH_AUTH_SOCK` (used by Compose/Dockerfile for the `developer` user, `docker.sock` access, `known_hosts`, and the agent mount). You may see a one-time passphrase / Keychain / askpass prompt during that step; you should not need to run a separate shell script.

**Still useful:**

- **macOS:** add to `~/.ssh/config` so later opens often skip prompts:
  ```
  Host *
    AddKeysToAgent yes
    UseKeychain yes
  ```
- **1Password SSH agent:** enable and unlock 1Password; initializeCommand reuses that agent when it already has identities.
- **GitHub without SSH:** `gh auth login` and HTTPS remotes (inside the container after start).
- **WSL:** use WSL end-to-end (`dev.containers.executeInWSL`); native Windows is not supported for this SSH flow.

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

Helper scripts live under [`.devcontainer/scripts/`](.devcontainer/scripts/) (see that directory’s `.directory_information.md`): `dockerfile/` (copied into the image), `initialize/` (host `initializeCommand`), and `shell/` (sourced from the workspace bind at runtime).

### Persisted data

Tool state uses **named Docker volumes** (macOS-friendly I/O). Each volume is also mounted under `.devcontainer/persist/` as a discoverability shortcut — see [`.devcontainer/persist/README.md`](.devcontainer/persist/README.md).

| Volume | Home path | Persist shortcut | Purpose |
|--------|-----------|------------------|---------|
| `super_projects_gemini-data` | `~/.gemini` | `persist/gemini` | Gemini CLI sessions/config |
| `super_projects_gh-data` | `~/.config/gh` | `persist/gh` | GitHub CLI auth |
| `super_projects_git-config` | `~/.config/git` | `persist/git` | Git XDG config |
| `super_projects_mise-data` | `~/.local/share/mise` | `persist/mise` | mise downloads and tool installs |
| `super_projects_chrome-devtools-mcp-profile` | `~/chrome-profile` | `persist/chrome` | Chrome logins, cookies, extensions |
| host ssh-agent socket | `/ssh-agent.sock` | — | Host-forwarded agent (private keys stay on the host) |
| host `known_hosts` (ro bind) | `~/.ssh/known_hosts` | — | Shared SSH host keys |

Named volumes survive container rebuilds. Remove one explicitly if you need a clean slate, for example:
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

These customizations belong in your company fork (see [Forking for your company](#forking-for-your-company)) so they are shared with the whole team via git:

- **Add/modify tools:** edit `.devcontainer/Dockerfile` and rebuild, or pin versions in `.mise.toml`.
- **Company-internal tools:** install them via Docker — bake them into `.devcontainer/Dockerfile`, or run them as additional services in `.devcontainer/compose.yaml` — rather than relying on manual per-developer setup.
- **Agent setups:** edit the shared profiles and attributes under `.agents/` and the MCP configs (`.cursor/mcp.json`, `.vscode/mcp.json`, `.mcp.json`, `.gemini/settings.json`, `.codex/config.toml`).
- **Add/modify extensions:** add extension IDs to the `customizations.vscode.extensions` array in `.devcontainer/devcontainer.json`.
- **Add/modify environment variables:** use `containerEnv` in `devcontainer.json` for variables that should always be set inside the container.
- **Project-specific services** take advantage of the GUI and add emulators / browsers / other gui tools to the dockerfile build.

## What's tracked in git

The `.gitignore` is configured to ignore everything **except** the files that define the development environment:

| Path | Purpose |
|------|---------|
| `.devcontainer/` | Dockerfile, compose, and devcontainer config |
| `.agents/` | Shared agent profiles and behavior attributes (templates for `agents.md`) |
| `.cursor/` / `.vscode/` / `.claude/` / `.codex/` / `.gemini/` | IDE and AI tool config (rules, settings, MCP wiring) |
| `.mcp.json` | Shared MCP server config |
| `.mise.toml` | Workspace-root tool versions |
| `README.md` | This file |
| `LICENSE` | Super Projects License (attribution required when reusing) |

The root `agents.md` is **not tracked**: each developer copies a shared profile from `.agents/agent_profiles/` and customizes it locally (see [`.agents/agent_profiles/README.md`](.agents/agent_profiles/README.md)).

Individual project directories cloned inside here are **not tracked** by this repo.

## License

This project is licensed under the [Super Projects License](LICENSE). The license applies only to the **super_projects scaffold** tracked in this repository (devcontainer, IDE config, `README.md`, `LICENSE`, and related files listed in [What's tracked in git](#whats-tracked-in-git)). It does **not** apply to files you or your company add — application code, databases, assets, and other project directories remain yours under whatever terms you choose.

When reusing or redistributing super_projects scaffold files, you must:

- Include a copy of the [Super Projects License](LICENSE) in any repository or distribution that incorporates that scaffold
- Give credit to **Samuel Anthony Frost** with a web URL to a page he manages that includes a way to contact him (for example [GitHub](https://github.com/SamuelFrost), [LinkedIn](https://www.linkedin.com/in/samuel-frost-0a8711a3), or [X](https://x.com/Samuelfrost7)). (Including the SUPER PROJECTS LICENSE satisfies this requirement; the readme and such may be modified as needed)


## Simple example project: create a new Rails project inside your fork
<!-- note: the project is created as an untracked subdirectory of this repo (the parent-directory pattern). Using this repo as a monorepo is no longer a recommended pattern. If you renamed your fork, the super_projects names below will already reflect your project name. -->

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

# super_projects

A containerized parent-directory environment for software development teams.

Fork this repository for your company, place your fork where you would normally keep your projects directory, and open it in VS Code or Cursor to get a fully configured development container your whole team can share.

## What this is

`super_projects` is designed to be your projects' parent directory. Rather than configuring each developer's machine individually, the dev environment (Docker, IDE settings, AI tooling) is codified here and shared via git.

It is a template meant to be forked once per company (or team), customized, and shared across the organization:

1. **Fork** this repo for your company.
2. **Set `${SUPER_PROJECTS_NAME}`** immediately so this clone does not share volumes with another default copy — see [Forking for your company](#forking-for-your-company).
3. **Customize** the agent setups and tools to match your company's needs.
4. Developers clone the company fork where they keep their projects; individual project repositories live inside it as untracked subdirectories.

Each company maintains its own version of the Docker image, devcontainer settings, agent setups, and IDE extensions — so every developer gets an identical, reproducible environment. Using the repo as a monorepo (tracking project code directly in it) is no longer a recommended pattern; keep projects as separate repositories cloned inside your fork.

## Forking for your company

The intended way to use this project is one fork per company (or team). Your fork becomes your organization's shared development environment: customize it, commit the changes, and every developer gets them on the next pull and container rebuild.

### 1. Set `${SUPER_PROJECTS_NAME}` (do this first)

`${SUPER_PROJECTS_NAME}` is the Compose project name. It determines the container (`${SUPER_PROJECTS_NAME}-devcontainer-1`), hostname (`${SUPER_PROJECTS_NAME}`), network (`${SUPER_PROJECTS_NAME}_default`), named-volume prefix (`${SUPER_PROJECTS_NAME}_gh-data`, `${SUPER_PROJECTS_NAME}_chrome-devtools-mcp-profile`, …), host ssh-agent socket (`$HOME/.cache/${SUPER_PROJECTS_NAME}-ssh-agent.sock` on WSLg, otherwise `$XDG_RUNTIME_DIR/${SUPER_PROJECTS_NAME}-ssh-agent.sock`), and the Cursor worker hint (`${SUPER_PROJECTS_NAME}_devcontainer`).

Those volumes hold GitHub CLI auth tokens, the Chrome profile (logins and cookies), Cursor CLI auth/session state, and git config. If two clones use the same `${SUPER_PROJECTS_NAME}` on one Docker daemon, they silently **share** that state. In other words, the project will share volumes and network space with any other clone with the same name on the same Docker daemon.

Copy the tracked example to a gitignored override and set the name (`acme_projects` is used below). Optionally set `${SUPER_PROJECTS_WORKDIR}` (container path `/${SUPER_PROJECTS_WORKDIR}`, default `workspaces`):

<<<<<<< HEAD
```sh
cp .devcontainer/.env.namespace_override.example .devcontainer/.env.namespace_override
```
=======
- `.devcontainer/compose.yaml`
  - `name: "super_projects"` → `name: "acme_projects"` — the Compose project name. This is the name that matters most: it determines the container name (`acme_projects-devcontainer-1`) and the named-volume prefix (`acme_projects_gh-data`, `acme_projects_chrome-devtools-mcp-profile`, …), which is what prevents volume sharing between forks.
  - `hostname: super_projects` → `hostname: acme_projects` — the container's hostname.
  - `super_projects_default` → `acme_projects_default` in all three network entries: the service's `networks:` list, the top-level `networks:` key, and its `name:`.
  - While editing, also update the comments quoting `docker volume rm super_projects_…` so they stay copy-pasteable.
- `.cursor/mcp.json`, `.vscode/mcp.json`, `.mcp.json`, `.gemini/settings.json`, `.codex/config.toml`
  - Replace the container name `super_projects-devcontainer-1` with `acme_projects-devcontainer-1` (one occurrence in each file). These configs `docker exec` into the container by name, so a mismatch with the Compose project name breaks the chrome-devtools MCP server.
- `.devcontainer/devcontainer.json`
  - `"name": "super_projects"` → `"name": "acme_projects"` — the label VS Code / Cursor shows for the devcontainer.
>>>>>>> fd1df5b (Document nested Compose apps as http://localhost in the parent Chrome.)

```
SUPER_PROJECTS_NAME=acme_projects
SUPER_PROJECTS_WORKDIR=workspaces
```

Then start the container — `initializeCommand` reads `SUPER_PROJECTS_NAME` and `SUPER_PROJECTS_WORKDIR` from the override and writes generated `.devcontainer/.env` (bind-mount vars plus those keys and a `COMPOSE_PROJECT_NAME` mirror so Compose and the image build pick them up). Do not edit the name or workdir in generated `.env`; it is overwritten on every initialize.

`${SUPER_PROJECTS_WORKDIR}` sets Dockerfile `WORKDIR`, the workspace bind mount, persist shortcuts, and Compose `working_dir`. Changing it also requires updating `"workspaceFolder"` in `.devcontainer/devcontainer.json` (JSON cannot interpolate the override). Changing `SUPER_PROJECTS_WORKDIR` needs an image rebuild (`devcontainer up --remove-existing-container` or Rebuild Container).

`devcontainer.json` `"name"` stays `super_projects` (IDE label only). MCP configs `docker compose … exec` the `devcontainer` service and do not hardcode `${SUPER_PROJECTS_NAME}-devcontainer-1`. Leave `LICENSE` and the attribution text in this README's [License](#license) section as they are: they refer to the original project.

**Manual Compose** always uses `--project-directory .devcontainer` so generated `.env` is loaded from `.devcontainer/`, not from the repo-root cwd. Initialize must have run after the override exists (VS Code / Cursor / `devcontainer up` already do this):

```sh
docker compose -f .devcontainer/compose.yaml --project-directory .devcontainer down
```

Do not set process-level `COMPOSE_PROJECT_NAME`; it overrides compose `name:` and the container name can diverge from hostname, network, and volumes.

**Changing an existing `${SUPER_PROJECTS_NAME}`** does not migrate state. `compose down` the **old** project first; `gh` / Chrome / Cursor volumes look wiped because they stay under the old prefix. Orphans remain until `docker volume rm ${SUPER_PROJECTS_NAME}_…`.

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

### Pulling in upstream changes

Your fork can keep receiving improvements from the original project. Add the upstream repository as a remote once:

```sh
git remote add upstream git@github.com:SamuelFrost/super_projects.git
```

Then, whenever you want to sync:

```sh
git fetch upstream
git checkout main
git merge upstream/main
```

A merge is preferred over a rebase because your fork's `main` is shared history that your whole team pulls from.

Things to watch for when merging:

- **Your customizations.** Changes you made to the Dockerfile, `.mise.toml`, agent profiles, and MCP configs (steps 2 and 3) may conflict with upstream edits to the same files; keep your company's version and port over anything useful from upstream. `${SUPER_PROJECTS_NAME}` lives in gitignored `.devcontainer/.env.namespace_override`, so upstream merges do not overwrite it.
- **Rebuild after merging.** If `.devcontainer/` changed, everyone should rebuild (_Dev Containers: Rebuild Container_, or `devcontainer up --remove-existing-container`) to pick up the new image and settings.

Push the merged result to your fork so the whole team receives the update.

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux)
- Atleast one of the following: 
  - [Dev Containers CLI](https://github.com/devcontainers/cli)
  - [VS Code](https://code.visualstudio.com/download) (with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers))
  - [Cursor](https://cursor.com/download) (with the Dev Containers extension)

Fork this repo for your company and set `${SUPER_PROJECTS_NAME}` first (see [Forking for your company](#forking-for-your-company)), then clone your fork where you keep your projects — it can be the parent directory of all your projects or just a few select ones.
```sh
git clone git@github.com:<your-company>/<your-fork>.git
```

---

### Option A — CLI (no IDE required)

```sh
# Build and start (runs initializeCommand → .devcontainer/scripts/shell/initializeCommand.sh, then builds + starts)
devcontainer up --remove-existing-container

# Open a shell inside the container
devcontainer exec bash

# Stop
docker compose -f .devcontainer/compose.yaml --project-directory .devcontainer down
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

Unlocking happens automatically in **`initializeCommand`** (`.devcontainer/scripts/shell/initializeCommand.sh`) before the container starts — the same hook used by **VS Code**, **Cursor** (“Reopen in Container”), and **`devcontainer up`**. That script runs `ensure-host-ssh-agent` (select or start the host agent using the `${SUPER_PROJECTS_NAME}` socket path from `.env.namespace_override`; may prompt once to unlock keys) and `write-devcontainer-env` (writes `.devcontainer/.env` with bind-mount vars plus `SUPER_PROJECTS_NAME`, a `COMPOSE_PROJECT_NAME` mirror, and `SUPER_PROJECTS_WORKDIR`). You may see a one-time passphrase / Keychain / askpass prompt during that step; you should not need to run a separate shell script.

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
- `.cursor/mcp.json` wires up the official [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp) via `docker compose … exec` into the `devcontainer` service and `mise`, so the MCP server connects to Chrome at `127.0.0.1:9223` inside the container. Optional host publication of the debugging port is disabled by default in Compose.
- [mise](https://mise.jdx.dev) — universal version manager for Ruby, Node, Python, Go, Java, and more
- Recommended extensions and settings for VS Code and Cursor
- TODO: add ruby-lsp, stimulus-lsp, and herb-lsp for language servers

The VNC/Chrome stack starts automatically when the container starts and can be restarted at any time by running `start-vnc` inside the container.

Helper scripts live under [`.devcontainer/scripts/`](.devcontainer/scripts/) (see that directory’s `.directory_information.md`): `dockerfile/` (copied into the image) and `shell/` (host `initializeCommand` and runtime shell helpers).

### Compose apps at `localhost`

A docker compose stack within the devcontainer (for example the [Rails sample app](.samples/rails_sample_app/rails_sample_app_initialization.md)) is reachable in the parent desktop Chrome at the same `http://localhost:<port>` URL as on the host. Publish the port in the project's Compose file; `start-localhost-forwards` mirrors it onto `127.0.0.1` inside this container. See [`.devcontainer/localhost-forwards.md`](.devcontainer/localhost-forwards.md).

`.devcontainer/.env` is generated on the host by `initializeCommand` and is gitignored. Set `${SUPER_PROJECTS_NAME}` and `${SUPER_PROJECTS_WORKDIR}` in `.devcontainer/.env.namespace_override` (copy the `.example`); initialize copies those two keys into `.env`. VS Code, Cursor, and `devcontainer up` regenerate `.env` each time; if you run Compose by hand, re-run `.devcontainer/scripts/shell/initializeCommand.sh` on the host first, then always pass `--project-directory .devcontainer`.

### Persisted data

Tool state uses **named Docker volumes** (macOS-friendly I/O). Each volume is also mounted under `.devcontainer/persist/` as a discoverability shortcut — see [`.devcontainer/persist/README.md`](.devcontainer/persist/README.md).

| Volume | Home path | Persist shortcut | Purpose |
|--------|-----------|------------------|---------|
| `${SUPER_PROJECTS_NAME}_gemini-data` | `~/.gemini` | `persist/gemini` | Gemini CLI sessions/config |
| `${SUPER_PROJECTS_NAME}_gh-data` | `~/.config/gh` | `persist/gh` | GitHub CLI auth |
| `${SUPER_PROJECTS_NAME}_git-config` | `~/.config/git` | `persist/git` | Git XDG config |
| `${SUPER_PROJECTS_NAME}_mise-data` | `~/.local/share/mise` | `persist/mise` | mise downloads and tool installs |
| `${SUPER_PROJECTS_NAME}_chrome-devtools-mcp-profile` | `~/chrome-profile` | `persist/chrome` | Chrome logins, cookies, extensions |
| `${SUPER_PROJECTS_NAME}_cursor-data` | `~/.cursor` | `persist/cursor` | Cursor CLI auth/session state, agent transcripts, MCP config, skills |
| host ssh-agent socket | `/ssh-agent.sock` | — | Host-forwarded agent (private keys stay on the host) |
| host `known_hosts` (ro bind) | `~/.ssh/known_hosts` | — | Shared SSH host keys |

Named volumes survive container rebuilds. Remove one explicitly if you need a clean slate, for example:
```sh
docker volume rm ${SUPER_PROJECTS_NAME}_chrome-devtools-mcp-profile
```

### Tool version management (mise)

`mise` is pre-installed and activated in every shell. Configure the tools your project needs by editing `.mise.toml` or including a `mise.toml` or `.tool-versions` file in the a project's directory see [mise documentation](https://mise.jdx.dev/getting-started.html) for more details.

Tools defined in the top level directory `.mise.toml` are installed automatically when the container starts (`mise install` in `compose.yaml`). Note: downloads and installs are stored in the `mise-data` Docker volume, so they will persist across container rebuilds unless you explicitly remove the volume with `docker volume rm ${SUPER_PROJECTS_NAME}_mise-data`.

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
| `.samples/` | Practical example project setup docs for common use cases (for example the [Rails sample app](.samples/rails_sample_app/rails_sample_app_initialization.md)) |
| `LICENSE` | Super Projects License (attribution required when reusing) |

The root `agents.md` is **not tracked**: each developer copies a shared profile from `.agents/agent_profiles/` and customizes it locally (see [`.agents/agent_profiles/README.md`](.agents/agent_profiles/README.md)).

Individual project directories cloned inside here are **not tracked** by this repo.

## License

This project is licensed under the [Super Projects License](LICENSE). The license applies only to the **super_projects scaffold** tracked in this repository (devcontainer, IDE config, `README.md`, `LICENSE`, and related files listed in [What's tracked in git](#whats-tracked-in-git)). It does **not** apply to files you or your company add — application code, databases, assets, and other project directories remain yours under whatever terms you choose.

When reusing or redistributing super_projects scaffold files, you must:

- Include a copy of the [Super Projects License](LICENSE) in any repository or distribution that incorporates that scaffold
- Give credit to **Samuel Anthony Frost** with a web URL to a page he manages that includes a way to contact him (for example [GitHub](https://github.com/SamuelFrost), [LinkedIn](https://www.linkedin.com/in/samuel-frost-0a8711a3), or [X](https://x.com/Samuelfrost7)). (Including the SUPER PROJECTS LICENSE satisfies this requirement; the readme and such may be modified as needed)

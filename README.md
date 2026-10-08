# super_projects

A containerized parent-directory environment for software development teams.

`super_projects` is a template for a containerized development environment designed to be your projects' parent directory. Rather than the traditional approach of configuring each machine individually or per project, the environment (Docker, tools, desktop GUI, AI tooling, internal company tools, common tooling, etc.) is codified here and shared via git.

It is intended to be used as a template for your company's work environment with convenient tools for development and enhancing AI agent capabilities for every day tasks available by default.

Projects are meant to live as separate, repositories inside this folder untracked by this repository.

## Getting started

Clone this repository and open it in your preferred editor (VS Code, Cursor, Dev Containers CLI, or Docker Compose directly) to get a fully configured development container your whole team/organization can share.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux)
- Any of:
  - VS Code / Cursor (with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers))
  - [Dev Containers CLI](https://github.com/devcontainers/cli) (`devcontainer`)
  - Plain Docker Compose via `./not_devcontainer`

<details>
<summary>Fork and rename (optional, recommended one time setup per organization)</summary>

### 1. Fork the repository

This creates a copy of the repository under your account/organization using standard Git commands, while keeping a link to `upstream` for future updates:

1. Create a new, empty repository on your Git hosting server (e.g. GitHub or GitLab) for your company/account (e.g. `git@github.com:<your-company>/super_projects.git`).

2. Clone this repository and enter it:
   ```sh
   git clone https://github.com/SamuelFrost/super_projects.git
   cd super_projects
   ```

3. Rename `origin` to `upstream` so you can pull future updates:
   ```sh
   git remote rename origin upstream
   ```

4. Set your new repository as `origin`:
   ```sh
   git remote add origin git@github.com:<your-company>/super_projects.git
   ```

5. Push all branches and tags to your new repository:
   ```sh
   git push -u origin --all
   git push --tags
   ```

*(To pull upstream updates later: `git fetch upstream && git merge upstream/main`)*

*(Alternatively, you can fork via the GitHub UI and clone your fork).*

### 2. (Recommended, not required) Customize name

By default, the project runs under the name `super_projects`. Change the `.devcontainer/docker_compose_configuration_customizations/naming/compose.naming.yaml` file to set a custom name for your project. 

- If you have a special use-case and have multiple checkouts or otherwise need a different namespace on one machine, set a custom name in `.devcontainer/docker_compose_configuration_customizations/naming/compose.naming.override.yaml` so they do not share Docker containers, volumes or networks.

</details>

<details>
<summary>Clone the repository</summary>

```sh
git clone git@github.com:SamuelFrost/super_projects.git
cd super_projects
```

</details>

### Starting and stopping services

- **VS Code / Cursor:** Open the directory and click **Reopen in Container**.
- **CLI (`devcontainer`):**
  ```sh
  devcontainer up --remove-existing-container
  devcontainer exec bash
  ```
- **CLI (Docker Compose):**
  ```sh
  ./not_devcontainer up -d
  ./not_devcontainer exec devcontainer bash
  ```

To stop: `./not_devcontainer down`.

### Accessing the container's GUI and CLI

- **GUI:** Open `http://localhost:6080/vnc.html` in your browser and press **Connect**.
- **CLI and miscellaneous cli execution:** Run `devcontainer exec bash` to get a shell in the container.
- **VS Code or Cursor:** Ensure the dev containers extension is installed and open the project folder. Remote - Containers will automatically detect the devcontainer and prompt you to open it - follow the prompts to open the project in the container.
- **vim:** Run `devcontainer exec vim` to edit files in the container.
note: while many IDEs can be configured to be installed and opened on the container, you will probably get the best experience by installing your preferred IDE on the host machine and open it on the container via the IDE's remote connection feature.

## Features & details

The devcontainer is an **Ubuntu 24.04** image with:

- `git`, `gh` (GitHub CLI), `openssh-client`
- Docker CLI + Compose (Docker outside of Docker via socket mount) + Devcontainer CLI
- Node.js, npm, Python 3
- [mise](https://mise.jdx.dev) — universal version manager for Ruby, Node, Python, Go, and more
- Desktop GUI (XFCE + VNC + noVNC) available in your browser at `http://localhost:6080/vnc.html`
- Google Chrome with remote debugging on port 9223 (used by MCP tools like [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp))
- [Localhost Forward Proxy](https://github.com/docker/localhost-forward-proxy) for port forwarding to your projects so they can be accessed from the container's browser at `http://localhost:<port>` in addition to the standard docker network routes.
- AI tooling configurations for Gemini, Cursor, VS Code, Claude, and Codex.
- Unobtrusive collection of useful attributes to guide agent behavior.

### SSH agent forwarding

Host SSH keys are forwarded into the container at `/ssh-agent.sock` — private keys never leave your host.

- **macOS:** Add `AddKeysToAgent yes` and `UseKeychain yes` to `~/.ssh/config`.
- **1Password:** Enable 1Password's SSH agent; it is automatically detected and used.
- **WSL2:** Use WSL directly (`dev.containers.executeInWSL`).

### Persisted volumes

State is preserved across container rebuilds via named Docker volumes:

| Volume | Mount in container | Purpose |
|--------|-------------------|---------|
| `<name>_gemini-data` | `~/.gemini` | Gemini CLI sessions/config |
| `<name>_gh-data` | `~/.config/gh` | GitHub CLI auth |
| `<name>_git-config` | `~/.config/git` | Git configuration |
| `<name>_mise-data` | `~/.local/share/mise` | Downloaded tools & runtimes |
| `<name>_chrome-devtools-mcp-profile` | `~/chrome-profile` | Chrome browser logins & extensions |
| `<name>_cursor-data` | `~/.cursor` | Cursor CLI sessions & agent transcripts |

These volumes are also dual-mounted under `.devcontainer/persist/` inside the container for easy inspection. To wipe state, delete the corresponding Docker volume (e.g., `docker volume rm <name>_gh-data`).

## Customization

- **Tools & runtimes:** Edit `.mise.toml` or add project-level `.mise.toml` files.
- **System packages:** Adjust installations in `.devcontainer/Dockerfile`.
- **Extensions:** Add extension IDs to `customizations.vscode.extensions` in `.devcontainer/devcontainer.json`.
- **AI agents & MCP:** Configure templates and attributes for agents `.agents/` and your preferred AI providers in `.cursor/`, `.vscode/`, `.gemini/`, `.codex/` etc.

## What's tracked in git

| Path | Purpose |
|------|---------|
| `.devcontainer/` | Dockerfile, compose, and devcontainer configuration |
| `.agents/` | Shared AI agent templates |
| `.cursor/`, `.vscode/`, `.gemini/`, `.codex/` | IDE & AI tool configs |
| `.mise.toml` | Default tool versions |
| `not_devcontainer` | Helper script to run Docker Compose matching devcontainer configuration |
| `README.md` | This file |
| `LICENSE` | Super Projects License |

The root `agents.md` and cloned project subdirectories are untracked.

## License

This project is licensed under the [Super Projects License](LICENSE). The license applies only to the **super_projects scaffold** tracked in this repository (devcontainer, IDE config, `README.md`, `LICENSE`, and related files listed in [What's tracked in git](#whats-tracked-in-git)). It does **not** apply to files you or your company add — application code, databases, assets, and other project directories remain yours under whatever terms you choose.

When reusing or redistributing super_projects scaffold files, you must:

- Include a copy of the [Super Projects License](LICENSE) in any repository or distribution that incorporates that scaffold
- Give credit to **Samuel Anthony Frost** with a web URL to a page he manages that includes a way to contact him (for example [GitHub](https://github.com/SamuelFrost), [LinkedIn](https://www.linkedin.com/in/samuel-frost-0a8711a3), or [X](https://x.com/Samuelfrost7)). (Including the SUPER PROJECTS LICENSE satisfies this requirement; the readme and such may be modified as needed)

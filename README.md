# super_projects

A containerized parent-directory environment for software development teams.

`super_projects` is a template for a containerized development environment designed to be your projects' parent directory. Rather than the traditional approach of configuring each machine individually or per project, the environment (Docker, tools, desktop GUI, AI tooling, internal company tools, common tooling, etc.) is codified here and shared via git.

It is intended to be used as a template for your company's work environment with convenient tools for development and enhancing AI agent capabilities for every day tasks available by default.

Projects are meant to live as separate, repositories inside this folder untracked by this repository.

## Getting started

Clone this repository and open it with an IDE that supports Dev Containers, or use the Dev Containers CLI, to get a fully configured development container your whole team/organization can share.

### Prerequisites

- Linux or macOS. On Windows, use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install)
- Docker installed and running. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- An IDE with Dev Container support is highly recommended

<details>
<summary>IDEs with Dev Container support</summary>

- **[Visual Studio Code](https://code.visualstudio.com/docs/devcontainers/containers)** — [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
- **Cursor** — Dev Containers extension included in Cursor.
- **[Zed](https://zed.dev/docs/dev-containers)** — native support when `.devcontainer/devcontainer.json` is present (Docker or Podman).
- **[IntelliJ IDEA](https://www.jetbrains.com/help/idea/connect-to-devcontainer.html)** — local Docker or remote SSH. PyCharm, GoLand, WebStorm, CLion, PhpStorm, Rider, and RubyMine can use the same flow by selecting that IDE backend, or connect through [JetBrains Gateway](https://www.jetbrains.com/remote-development/).
- **Visual Studio 2022** (17.4+) — C++ projects that use CMake Presets, with the Linux and embedded development with C++ workload. The container is treated as a remote Linux target.
- **Emacs** — community package [`devcontainer.el`](https://github.com/johannes-mueller/devcontainer.el) (MELPA). It needs the Dev Containers CLI.
- **[GitHub Codespaces](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers)**, **CodeSandbox**, and **Ona** (formerly Gitpod) — hosted environments that read `devcontainer.json`.

[DevPod](https://github.com/loft-sh/devpod) can build the container and open it in VS Code, the JetBrains suite, Zed, or any editor that connects over SSH.

The setup steps below use VS Code, Cursor, or the Dev Containers CLI. The [spec’s supporting-tools list](https://containers.dev/supporting) is the current source for which tools implement `devcontainer.json`.

</details>

If you're happy to not use an IDE, or otherwise prefer a terminal based approach, you can use the Dev Containers CLI (`devcontainer`) or the plain Docker Compose option via running [`./not_devcontainer`](./not_devcontainer). You may use the CLI to run `vim` (included by default) or your preferred CLI editor. It's not recommended, but you can also interact with the desktop GUI via the VNC server at `http://localhost:6080/vnc.html`.

### Initial setup

<details>
<summary>Fork and rename (optional, recommended one time setup per organization)</summary>

#### 1. Fork the repository

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

#### 2. (Recommended, not required) Customize name

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

- For IDEs that support Dev Containers: Open the directory and execute the command to Reopen it in the container. For vsCode and Cursor, use ctrl + shift + p to open the command palette and type something along the lines of `Reopen in Container` or `Rebuild Container` and select the option.
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

To stop: `./not_devcontainer down` or otherwise perform a docker compose down equivalent such as docker desktop's stop button.

### Accessing the container's GUI and CLI

- **GUI:** Open `http://localhost:6080/vnc.html` in your browser and press **Connect**.
- **CLI and miscellaneous cli execution:** Run `devcontainer exec bash` or `./not_devcontainer exec devcontainer bash` to get a shell in the container.
- **IDE:** Open the project folder in your preferred IDE that supports Dev Containers. VS code and Cursor will automatically detect the devcontainer and prompt you to open it - follow the prompts to open the project in the container.

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

<details>
<summary>To fully remove the containers and all associated data:</summary>

Note, if you have set up projects with multiple names, you will need to run this command for each namespace.

#### To fully remove the containers and volumes:

This stops `devcontainer` and `localhost_forward_proxy`, removes the project network, and deletes the named volumes in the table above (Gemini, GitHub CLI auth, git config, mise installs, Chrome profile, and Cursor state). The built images stay, so the next start can reuse them.

```sh
./not_devcontainer down -v
```

#### To also remove this project's images:

Same cleanup as above, and deletes the images Compose built for this project, plus containers left behind by services that are no longer in the Compose file.

```sh
./not_devcontainer down -v --rmi all --remove-orphans
```

</details>

## Customization

### Docker compose customizations

Docker compose has a chain of override files to modularize common customizations.

<details>
<summary>Namespace customization</summary>

The override file is `.devcontainer/docker_compose_configuration_customizations/naming/compose.naming.override.yaml`, it is recommended to copy the [example file](.devcontainer/docker_compose_configuration_customizations/naming/compose.naming.override.example.yaml) and modify the name and network name fields to your needs.

```sh
cp .devcontainer/docker_compose_configuration_customizations/naming/compose.naming.override.example.yaml .devcontainer/docker_compose_configuration_customizations/naming/compose.naming.override.yaml
```

This is useful if you want to set up multiple codebases that can act mostly independently of each other by setting the docker compose override file to use a different namespace.

*If you want to make these changes the new default for your whole team/organization*, you can write this customization to the `.devcontainer/docker_compose_configuration_customizations/naming/compose.naming.yaml` file instead.

</details>

<details>
<summary>Miscellaneous overrides</summary>

You may have special uses that require further customization of the devcontainer. This is done by writing your configuration to the `.devcontainer/docker_compose_configuration_customizations/miscellaneous_overrides/compose.miscellaneous.override.yaml` file.

*If you want to make these changes the new default for your whole team/organization*, you can write this customization to the `.devcontainer/docker_compose_configuration_customizations/miscellaneous_overrides/compose.miscellaneous.yaml` file instead. Directly modifying the `.devcontainer/compose.yaml` file will achieve the same result, but may be more difficult to maintain if you want to pull upstream changes from the super_projects repository in the future.

</details>

Other compose files are intended to be programmatically generated by the [startup script](.devcontainer/scripts/shell/initializeCommand.sh).

### Shared tools and runtimes

You are encouraged to modify everything to your own company's needs. Some likely changes you will want to make are:
- **Tools & runtimes:** Edit `.mise.toml` or add project-level `.mise.toml` files.
- **System packages:** Add or remove installations in `.devcontainer/Dockerfile`.
- **Extensions:** Add extension IDs to `customizations.vscode.extensions` in `.devcontainer/devcontainer.json`.
- **AI agents & MCP:** Configure templates and attributes for agents `.agents/` and your preferred AI providers in `.cursor/`, `.vscode/`, `.gemini/`, `.codex/` etc.
- **Sandboxing:** Remove host machine access methods for more tightly controlled environments. (recommended steps coming soonish / when I get around to it)

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

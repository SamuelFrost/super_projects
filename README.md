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

### Initialize command

[`initializeCommand.sh`](.devcontainer/scripts/shell/initializeCommand.sh) runs on the host before the container starts. It currently is responsible for setting up the docker compose configurations for the devcontainer based on the host machine.

<details>
<summary>Docker compose configurations generated by initializeCommand</summary>

#### SSH agent forwarding

For developer convenience, the devcontainer automatically forwards your host's SSH agent into the container at `/ssh-agent.sock`. This lets tools like Git in the container use your existing SSH keys without copying private keys into Docker.

<details>
<summary>How to set up your Host Machine's SSH keys so they can be used in the container</summary>

The devcontainer looks for keys on your host in this order:

- **Existing agent:** If `SSH_AUTH_SOCK` is already set in your host environment and has unlocked keys, it is used directly.
- **1Password:** Turn on the 1Password SSH agent. If unlocked, the devcontainer detects and uses it automatically.
- **macOS Keychain:** Add the following to `~/.ssh/config` so macOS can unlock keys without needing an interactive terminal:
  ```ssh-config
  AddKeysToAgent yes
  UseKeychain yes
  ```
- **Default SSH keys (`~/.ssh/id_*`):** If no agent has keys loaded, the startup script starts a dedicated agent and tries to load standard keys (`id_ed25519`, `id_rsa`, etc.). It will prompt for your passphrase via terminal, macOS Keychain, or a GUI askpass dialog if available.
- **Windows / WSL2:** The devcontainer must run inside WSL because container mounts require a Linux Unix socket (Windows OpenSSH uses named pipes, which cannot be forwarded here). If you run VS Code or Cursor from Windows, ensure your user `settings.json` has:
  ```json
  "dev.containers.executeInWSL": true
  ```
  *(Note: Must be in user settings, as workspace settings are ignored for this setting.)*

</details>

<details>
<summary>Technical details (how socket forwarding works)</summary>

Before starting the container, `initializeCommand` runs [`write-compose-ssh-agent-socket`](.devcontainer/docker_compose_configuration_customizations/ssh_agent_socket/write-compose-ssh-agent-socket) (also executed by `./not_devcontainer`):

1. **Socket discovery:** It checks for active keys (`ssh-add -l`) across:
   1. `$SSH_AUTH_SOCK`
   2. 1Password agent sockets (`~/Library/Group Containers/...` or `~/.1password/agent.sock`)
   3. A project-managed socket in `$XDG_RUNTIME_DIR/` or `~/.cache/` (named after the Compose project)
2. **Fallback loading:** If all agents are empty, it launches or reuses the project-managed socket and attempts to add standard keys from `~/.ssh/`.
3. **Mount generation:** It writes `compose.ssh-agent-socket.yaml`, bind-mounting the selected socket to `/ssh-agent.sock` inside the container.
4. **Nested containers:** When running inside another devcontainer, it automatically resolves `HOST_SSH_AUTH_SOCK` from the outer environment so the bind mount refers to the actual Docker host path.

</details>

#### SSH known hosts

Your host's `~/.ssh/known_hosts` is mounted into the container as read-only at `/home/developer/.ssh/known_hosts`. Any host you have already trusted on your host machine will work immediately inside the container.

<details>
<summary>Adding or trusting new hosts</summary>

Because the container mount is read-only, new hosts must be added from your host machine:

- **Scan and add automatically (host terminal):**
  ```sh
  ssh-keyscan github.com >> ~/.ssh/known_hosts
  ```
- **Or connect once from the host:** SSH to the remote server from your host terminal and accept the fingerprint prompt.

The container reflects updates to `~/.ssh/known_hosts` immediately without needing a rebuild or restart.

</details>

<details>
<summary>Technical details (how known_hosts mounting works)</summary>

During startup, `initializeCommand` (or `./not_devcontainer`) runs [`write-compose-ssh-known-hosts`](.devcontainer/docker_compose_configuration_customizations/ssh_known_hosts/write-compose-ssh-known-hosts):

1. **Host path resolution:** Locates `$HOME/.ssh/known_hosts` on your host machine (ensuring the file exists so Docker doesn't mistakenly create a directory).
2. **Mount generation:** Generates `compose.ssh-known-hosts.yaml`, mounting that file to `/home/developer/.ssh/known_hosts:ro`.
3. **Nested containers:** When running inside another devcontainer, it reads `HOST_HOME_DIR` from the parent container's config so the volume mount resolves to the true host filesystem path.

</details>

#### Docker socket access and workspace directory mounting

The host's `/var/run/docker.sock` is mounted into the container at the same path, so `docker` commands inside the container use the host daemon. 

The repository root is bind-mounted to `/workspaces` inside the container using an explicit host path rather than a simple relative mount (like `../:/workspaces`). That path is also recorded as `HOST_WORKSPACE_DIR`. Docker commands run inside the container use the host daemon, which cannot mount `/workspaces`, so they pass `HOST_WORKSPACE_DIR` instead.

When creating docker compose configurations to run inside the container, you will need to host volumes as the `${HOST_WORKSPACE_DIR:-..}/<directory-name>:<path-inside-the-service-container>`. This uses the project directory with the `..` fallback so you can still run it directly on the host machine if desired.

*note: I'm considering removing this feature/approach in the future in favor of a docker-inside-of-docker approach*

#### User permissions

Inside the devcontainer you are the `developer` user. That user is created with your host user id, so files it creates in the mounted workspace are owned by you on the host. The id is set when the image is built.

The `developer` user also belongs to a `docker` group created with that socket's group id, which is what allows it to use the socket. The group id is set when the image is built, so a different socket group needs a rebuild.

</details>

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

All proprietary business logic, product code, secrets, and private infrastructure remain exclusively yours. The license includes a mutual permission clause (Section 5) that allows authors and maintainers to upstream generalized, sanitized developer tooling improvements (like generic devcontainer configurations, helper scripts, or workflow templates) without compromising any company's proprietary IP or confidential data.

When reusing or redistributing super_projects scaffold files, you must:

- Include a copy of the [Super Projects License](LICENSE) in any repository or distribution that incorporates that scaffold
- Give credit to **Samuel Anthony Frost** with a web URL to a page he manages that includes a way to contact him (for example [GitHub](https://github.com/SamuelFrost), [LinkedIn](https://www.linkedin.com/in/samuel-frost-0a8711a3), or [X](https://x.com/Samuelfrost7)). (Including the SUPER PROJECTS LICENSE satisfies this requirement; the readme and such may be modified as needed)

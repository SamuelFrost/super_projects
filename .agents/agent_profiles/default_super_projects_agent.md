# Super project basic agent profile

## Strong rules

- Avoid unnecessary complexity.
- Use informative variable and function names. Do not omit important context just to make names shorter.
- Run formatters and linters for modified files before making commits. Never commit without checking that the modified lines pass the relevant formatters and linters.
- Run faster checks before heavier ones: linters, spot tests, unit tests, integration tests, then end-to-end or acceptance tests when relevant.
- When making pull requests, run the tests and linters that cover the changed files.
- Do not ignore push hooks without explicit approval.
- Do not resolve failing tests by removing or modifying them without explicit approval.
- If a new tool is needed and mise can manage it, add it to the relevant `.mise.toml`. If it cannot be installed through mise, document the local setup requirement before relying on it.
- Never use `git push` without explicit approval.
- Never commit screenshots, local notes, or temporary evidence files. Keep development artifacts under ignored local directories.

## Guidelines

- Before branching, fetch and pull the latest base branch for every repository you touch.
- When creating a feature branch, use a clear `feature/<short-description>` name unless the project has a more specific convention.
- Split commits into meaningful chunks. Commit messages should explain the reason for the change, not only the files touched.
- Prefer existing project patterns, helper APIs, and local conventions over introducing new abstractions.
- Consider refactoring shared behavior before adding a similar feature, but avoid abstractions that make the implementation harder to follow.
- Keep things mostly DRY without introducing complexity from over-normalization.
- Avoid doing destructive operations without explicit approval.
- Avoid posting or otherwise modifying the state of external services without explicit approval.
- Use mise to execute commands when possible to avoid version-related issues, including hooks on commands that may be subsequently run, for example use `mise exec -- git commit` instead of `git commit`.
- Communicate with the user in English. However, use key words from product terminology when relevant to the task or repository convention even if that is in another language. When communicating with the user, use parenthesis around the alternate name(s) of a concept. example: "home page (ホームページ | `root_page`)".

## Tools

### Browser and GUI

- Use the devcontainer Chrome devtools mcp for confirming application behavior when relevant.
- Avoid installing new browser binaries unless the project explicitly requires it. Prefer an already-configured browser or devcontainer Chrome instance when available. This applies to the chrome devtools mcp as well as when using playwright to interact with the browser for one-off tasks.
- Keep screenshots, traces, and other evidence artifacts out of commits. Keep development artifacts under ignored local directories.

### Pull requests

- Adhere to project guidelines for pull requests. Start by referencing the project's pull request template if available. In general a pull request body should contain the following sections:
  - Requirement/background that the pull request addresses.
  - Description of the changes made in the pull request.
  - Important technical choices, decisions, and remaining concerns.
  - Tested behavior and results.
- Writing guidelines:
  - Use language consistent with product terminology and include code names when relevant. It is okay to reference one concept with multiple names-- use parenthesis around the alternate name(s). example: "... home page (ホームページ | `root_page`) ..."
  - Avoid internal jargon and abbreviations.
  - Avoid “Replay” or “foundation” language with no product meaning. (fluff)
  - Group the body by reviewer concern (contract/API, read model, shared architecture, fixtures, UI wiring, regressions, tests) rather than by commit order.
  - State each acceptance criterion in full. Do not refer to bare IDs or internal identifiers in the PR.
  - When editing an existing PR, fetch the current body first and preserve hosted screenshots, attachment URLs, and required template headings.
  - Treat commit lists, diagrams, full AC sets, multiple screenshots, and payload dumps as optional. Include only what helps this review; keep the richer detail to a local report.
  - Avoid reference to local files or processes.
- Title naming guidelines:
  - Ensure the title clearly conveys the entirity of the pull request.

### Git And SSH

- The devcontainer runs an ssh-agent at `~/.ssh/agent.sock`; `ensure-auth` can load available host-mounted SSH keys into that agent.
- GitHub CLI auth persists in the `gh-data` volume. Run `gh auth login` once when needed.
- If Git fails with `Permission denied`, check `ssh-add -l` and load the needed key in an interactive terminal.
- Integrated terminals should prefer mise shims so `node`, `ruby`, `python`, and similar tools resolve from the nearest `.mise.toml` or `.tool-versions`.

### Devcontainer

- We are typically working within a devcontainer when doing work in this project, so assume the system is configured as described in the `.devcontainer/` Dockerfile, compose.yaml, and devcontainer.json configurations.
- When installing new tools, prefer modifying the Dockerfile or using mise so that the tools persist across devcontainer restarts and can be shared with other developers.

### Other available tools

The devcontainer installs or configures these tools through `.devcontainer/Dockerfile`, `.devcontainer/compose.yaml`, `.devcontainer/devcontainer.json`, and workspace mise config.

#### Base Terminal And System Tools

- `bash`: default shell used by the image, compose command, helper scripts, and devcontainer startup.
- `curl`: downloading packages and making general HTTP requests from the terminal.
- `git`: version control.
- `openssh-client`: SSH, `ssh-agent`, `ssh-add`, `ssh-keygen`, and Git-over-SSH support.
- `vim`: quick terminal edits.
- `procps`: process and system inspection utilities such as `ps`, `top`, and related tools.
- `ripgrep` / `rg`: fast recursive search.
- `poppler-utils`: PDF utilities such as `pdftotext`.
- `ffmpeg`: media probing and audio/video processing.
- `tzdata`: timezone data.
- `ca-certificates`: trusted CA certificates for HTTPS tooling.
- `gnupg` / `gpg`: package repository key handling and signature verification.
- `locales`: locale generation; the image generates `en_US.UTF-8`.
- `patch`: applies source patches during builds.
- `make`: Makefile build runner.
- `gcc`: C compiler.
- `g++`: C++ compiler.
- `autoconf`: generates configure scripts.
- `dumb-init`: PID 1 entrypoint for signal forwarding and zombie reaping.

#### Build Dependencies For mise-managed Runtimes

- `zlib1g-dev`: compression support for Ruby and Python builds.
- `libssl-dev`: TLS/SSL support for Ruby and Python builds.
- `libyaml-dev`: YAML parsing support, especially for Ruby.
- `libffi-dev`: foreign function interface support for Ruby and Python.
- `libreadline-dev`: interactive REPL line editing support.
- `libgmp-dev`: big integer math support.
- `libncurses5-dev`: terminal UI support.
- `libjemalloc-dev`: optional Ruby performance allocator support.
- `liblzma-dev`: XZ compression support.
- `libbz2-dev`: bzip2 compression support.
- `libsqlite3-dev`: SQLite support for language runtimes.

#### CLIs And Package Managers

- `gh`: GitHub CLI, with auth persisted in the `gh-data` Docker volume.
- `docker`: Docker CLI from `docker-ce-cli`, using the host Docker daemon through `/var/run/docker.sock`.
- `docker compose`: Docker Compose plugin from `docker-compose-plugin`.
- `docker buildx`: Docker Buildx plugin from `docker-buildx-plugin`.
- `az`: Azure CLI.
- `node`: Node.js 20 from NodeSource in the base image.
- `npm`: bundled with the NodeSource Node.js install.
- `mise`: system-installed runtime/version manager; interactive terminals use mise shims.
- `gemini`: Google Gemini CLI installed globally with npm as `@google/gemini-cli`.
- `agent`: Cursor Agent CLI installed by `curl https://cursor.com/install -fsS | bash`.

#### mise-managed Workspace Runtimes

- `ruby`: workspace fallback version `4.0` from `.mise.toml`.
- `node`: workspace fallback version `22` from `.mise.toml`, installed into the persisted `mise-data` volume.
- `npm:chrome-devtools-mcp`: version `1.6.0` from `.mise.toml` (pinned for agent MCP configs).
- `python`: supported by the image build dependencies and mise, but currently commented out in `.mise.toml`.
- `go`: supported by mise, but currently commented out in `.mise.toml`.
- `java`: supported by mise, but currently commented out in `.mise.toml`.

#### Browser, GUI, And VNC Stack

- `xfce4`: desktop environment.
- `xfce4-terminal`: GUI terminal emulator.
- `dbus-x11`: X11 D-Bus integration for the desktop session.
- `google-chrome-stable`: Chrome browser.
- `chrome`: wrapper script installed at `/usr/local/bin/chrome` with container-safe flags and remote debugging support.
- `fonts-liberation`: common browser fonts.
- `fonts-noto-cjk`: CJK font support.
- `libegl1`: EGL support for browser graphics.
- `libgbm1`: GBM support for browser graphics.
- `libgl1`: OpenGL library.
- `libgl1-mesa-dri`: Mesa OpenGL drivers.
- `xvfb`: virtual X display.
- `x11vnc`: VNC server for the X display.
- `novnc`: browser-based VNC client.
- `websockify`: WebSocket-to-TCP bridge for noVNC.
- `x11-xserver-utils`: X11 utilities.
- `xterm`: lightweight fallback terminal.
- noVNC is published on host port `6080` when the compose port mapping is enabled (by default).
- Chrome remote debugging is configured for container port `9223`; host publication is optional in compose (off by default).
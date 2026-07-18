# Domain context — available tools installed by the devcontainer

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

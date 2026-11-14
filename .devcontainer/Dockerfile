ARG UBUNTU_VERSION=24.04
FROM ubuntu:${UBUNTU_VERSION}

WORKDIR /workspaces

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Install core development tools and mise build dependencies.
# curl:           downloading packages and general HTTP from the terminal
# git:            version control
# openssh-client: Git/SSH via host-forwarded ssh-agent (private keys stay on the host)
# vim:            quick terminal edits when SSH'd in
# procps:         top, free, ps — system monitoring
# ripgrep:        fast recursive search via the `rg` command
# python3:        system Python for ad-hoc scripts (project interpreters still come from mise)
# socat:          extra TCP/UDP relay for one-off debugging
# poppler-utils:  pdftotext etc. — lets agents/scripts read PDFs as text
# ffmpeg:         probe/process video and audio (metadata, extract audio)
# tzdata:         timezone data (suppressed interactive prompt via ENV above)
# --- mise compile-from-source dependencies ---
# zlib1g-dev:     compression (Ruby, Python)
# libssl-dev:     TLS/SSL (Ruby, Python)
# libyaml-dev:    YAML parsing (Ruby)
# libffi-dev:     foreign function interface (Ruby, Python)
# libreadline-dev: interactive REPL line editing (Ruby, Python)
# libgmp-dev:     big integer math (Ruby)
# libncurses5-dev: terminal UI (Ruby)
# libjemalloc-dev: optional performance allocator (Ruby)
# liblzma-dev:    XZ compression (Python)
# libbz2-dev:     bzip2 compression (Python)
# libsqlite3-dev: embedded database (Python)
# patch:          applies source patches during ruby-build compilation
# make:           drives the C build process (runs Makefiles)
# gcc:            C compiler — required to build Ruby, Python, and most native gems
# g++:            C++ compiler — required for gems/extensions with C++ code
# autoconf:       generates ./configure scripts from Makefile.in templates
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
  curl \
  git \
  openssh-client \
  vim \
  procps \
  ripgrep \
  socat \
  python3 \
  poppler-utils \
  ffmpeg \
  tzdata \
  ca-certificates \
  gnupg \
  locales \
  zlib1g-dev \
  libssl-dev \
  libyaml-dev \
  libffi-dev \
  libreadline-dev \
  libgmp-dev \
  libncurses5-dev \
  libjemalloc-dev \
  liblzma-dev \
  libbz2-dev \
  libsqlite3-dev \
  patch \
  make \
  gcc \
  g++ \
  autoconf \
  && rm -rf /var/lib/apt/lists/*

# Route ssh/git clients to the host-forwarded agent even when SSH_AUTH_SOCK is unset.
RUN printf '%s\n' 'Host *' '  IdentityAgent /ssh-agent.sock' \
  > /etc/ssh/ssh_config.d/99-shared-agent.conf \
  && chmod 644 /etc/ssh/ssh_config.d/99-shared-agent.conf

# Generate the en_US.UTF-8 locale so tools that invoke perl (e.g. ruby-build) don't warn.
RUN locale-gen en_US.UTF-8

# Generate a stable machine-id so Chrome doesn't emit the "0 characters" warning.
RUN head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' > /etc/machine-id

# Build args: populated by initializeCommand with host `id -u` and `docker.sock` gid
ARG DEVELOPER_UID=501
ARG DOCKER_GID=1

# Ubuntu 24.04 ships a default `ubuntu` user at UID 1000; remove it before
# creating `developer` so there is no UID conflict when the host uid is 1000.
# Create docker group with the host's GID so the mounted docker.sock is accessible.
RUN userdel --remove ubuntu 2>/dev/null || true && \
    groupadd --gid ${DOCKER_GID} docker || groupadd --gid 1001 docker || groupadd docker || true

# Create developer user matching the host UID (updateRemoteUserUID in devcontainer.json can adjust UID at start)
RUN groupadd --system developer && \
  useradd --uid ${DEVELOPER_UID} --gid developer --create-home --shell /bin/bash developer && \
  usermod -aG docker developer

# Ensure developer owns their home directory.
# Pre-create directories that will be backed by named volumes so Docker
# initialises those volumes with developer ownership rather than root
# (Docker creates missing mount-point directories as root if they don't exist).
# ~/.ssh holds only known_hosts (host file bind); private keys are not mounted.
RUN mkdir -p /home/developer/chrome-profile \
             /home/developer/.local/share/mise \
             /home/developer/.local/state/mise \
             /home/developer/.config/gh \
             /home/developer/.config/git \
             /home/developer/.gemini \
             /home/developer/.ssh && \
    touch /home/developer/.ssh/known_hosts && \
    chmod 700 /home/developer/.ssh && \
    chown -R developer:developer /home/developer

# ------------------------------------------------------------------------------
# GitHub CLI (gh)
# ------------------------------------------------------------------------------
RUN install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && chmod a+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends gh \
  && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Docker CLI (outside-of-docker: uses the host daemon via mounted socket)
# Installs only the CLI + Compose plugin — no daemon.
# ------------------------------------------------------------------------------
RUN install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors https://download.docker.com/linux/ubuntu/gpg \
       -o /etc/apt/keyrings/docker.asc \
  && chmod a+r /etc/apt/keyrings/docker.asc
# /etc/os-release provides VERSION_CODENAME (e.g. "noble" for 24.04)
RUN . /etc/os-release && \
  printf "Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nSigned-By: /etc/apt/keyrings/docker.asc\n" \
    "${VERSION_CODENAME}" > /etc/apt/sources.list.d/docker.sources \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends \
       docker-ce-cli \
       docker-compose-plugin \
       docker-buildx-plugin \
  && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Azure CLI (az)
#   Installed from Microsoft's apt repository (deb822 format), matching the
#   manual install steps in the docs so the version is reproducible and the
#   layer stays cached.
#   Docs: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
# ------------------------------------------------------------------------------
RUN install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
  && chmod a+r /etc/apt/keyrings/microsoft.gpg
# /etc/os-release provides VERSION_CODENAME (e.g. "noble" for 24.04)
RUN . /etc/os-release && \
  printf "Types: deb\nURIs: https://packages.microsoft.com/repos/azure-cli/\nSuites: %s\nComponents: main\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/microsoft.gpg\n" \
    "${VERSION_CODENAME}" "$(dpkg --print-architecture)" \
    > /etc/apt/sources.list.d/azure-cli.sources \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends azure-cli \
  && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# HEAVY LAYERS — placed early so they are cached and never re-run when lighter
# things (Gemini CLI, startup scripts) change.
# ==============================================================================

# ------------------------------------------------------------------------------
# Desktop GUI: XFCE4
#   ~300 MB; almost never changes → own layer for stable caching.
#   dbus-x11:    X11 dbus integration required by the XFCE session manager.
#   xfce4-terminal: default terminal emulator for the desktop.
# ------------------------------------------------------------------------------
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
  xfce4 \
  xfce4-terminal \
  dbus-x11 \
  && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# VNC server stack
#   Xvfb:        headless virtual X display (DISPLAY=:99)
#   x11vnc:      shares the Xvfb display over VNC (port 5900)
#   novnc + websockify: bridge VNC → WebSocket for browser access (port 6080)
#   x11-xserver-utils: xsetroot and other X utilities
#   xterm:       lightweight fallback terminal
# ------------------------------------------------------------------------------
ENV DISPLAY=:99 \
    VNC_PORT=5900 \
    NOVNC_PORT=6080 \
    NOVNC_RESOLUTION=1920x1080 \
    CHROME_REMOTE_DEBUGGING_PORT=9223 \
    LIBGL_ALWAYS_SOFTWARE=1

# --- VNC server stack dependencies ---
# libegl1:        EGL library, needed for WebGL support in Chrome.
# libgbm1:        GBM library, needed for hardware acceleration in Chrome.
# libgl1:         OpenGL library, needed for graphics in Chrome.
# libgl1-mesa-dri: Mesa OpenGL drivers, needed for graphics in Chrome.
# novnc:          noVNC web client, needed for VNC access.
# websockify:     WebSocket to TCP proxy, needed for noVNC.
# x11-xserver-utils: X11 utilities, needed for X11 display management.
# x11vnc:         VNC server, needed for VNC access.
# xterm:          lightweight fallback terminal, needed for debugging.
# xvfb:          virtual X display, needed for headless Chrome.
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
  libegl1 \
  libgbm1 \
  libgl1 \
  libgl1-mesa-dri \
  novnc \
  websockify \
  x11-xserver-utils \
  x11vnc \
  xterm \
  xvfb \
  && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Google Chrome
#   Official repository supplies amd64 and arm64 packages.
#   fonts-liberation: core fonts Chrome needs for proper text rendering.
#   A wrapper at /usr/local/bin/chrome applies the container-required flags:
#     --enable-unsafe-swiftshader  Software WebGL (no GPU in the container).
#     --enable-features=WebMCP  WebMCP tools for chrome-devtools-mcp (Chrome 150+).
#   The namespace sandbox is enabled by .devcontainer/seccomp/desktop-sandboxes.json.
# ------------------------------------------------------------------------------
ARG TARGETARCH
RUN install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
  && chmod a+r /etc/apt/keyrings/google-chrome.gpg \
  && echo "deb [arch=${TARGETARCH} signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends \
       google-chrome-stable \
       fonts-liberation \
       fonts-noto-cjk \
       dumb-init \
  && rm -rf /var/lib/apt/lists/*

# Idempotent Chrome launcher.
# Checks the remote debugging endpoint to detect a running instance;
# starts Chrome only if it is not already up.
# Binds the remote debugging port on 0.0.0.0 so Docker port-publishing can
# forward it to the host, allowing host-side MCP clients to connect via npx.
# --remote-allow-origins=* lets chrome-devtools-mcp open the CDP WebSocket
# (Chrome 111+ rejects cross-origin upgrades without this flag).
COPY --chmod=0755 .devcontainer/scripts/dockerfile/chrome /usr/local/bin/chrome

# Point the XFCE application menu launcher at the wrapper so it also picks up
# all the flags above (including remote-debugging-port for MCP connectivity).
RUN sed -i \
  's|Exec=/usr/bin/google-chrome-stable|Exec=/usr/local/bin/chrome|g' \
  /usr/share/applications/google-chrome.desktop

# ==============================================================================
# LIGHTER / MORE FREQUENTLY UPDATED LAYERS
# ==============================================================================

# ------------------------------------------------------------------------------
# Node.js 24 LTS via NodeSource (Ubuntu ships an older Node; Gemini CLI and
# chrome-devtools-mcp require a current LTS).
# npm is bundled with the NodeSource nodejs package — no separate install needed.
# ------------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
  && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

# Herb LSP 0.11 starts a language server that requires vscode-html-languageservice,
# but the published extension does not include it. The editor installs that
# extension under the developer home directory, and Node walks upward from the
# server file until it reaches /home/developer/node_modules. The symlink makes
# that lookup succeed in every container built from this image. This can be
# removed once a Herb release ships a self-contained server or a way to
# run via mise managed software.
RUN mkdir -p /opt/herb-lsp-deps \
  && npm install --prefix /opt/herb-lsp-deps --omit=dev \
       vscode-html-languageservice@^5.1.0 \
  && ln -sfn /opt/herb-lsp-deps/node_modules /home/developer/node_modules

# ------------------------------------------------------------------------------
# Dev Containers CLI (devcontainer)
#   Create, build, and run dev containers from the terminal (up, exec, build, …).
#   Uses the host Docker daemon via the mounted socket.
#   Docs: https://github.com/devcontainers/cli
# ------------------------------------------------------------------------------
RUN npm install -g @devcontainers/cli

# ------------------------------------------------------------------------------
# mise — universal version manager for Ruby, Node, Python, Go, Java, etc.
#   Installed system-wide via apt; each developer's tool installs go in ~/.local.
#   Docs: https://mise.jdx.dev
# ------------------------------------------------------------------------------
RUN curl -fsSL https://mise.jdx.dev/gpg-key.pub \
       -o /etc/apt/keyrings/mise-archive-keyring.asc \
  && printf "deb [signed-by=/etc/apt/keyrings/mise-archive-keyring.asc] https://mise.jdx.dev/deb stable main\n" \
       > /etc/apt/sources.list.d/mise.list \
  && apt-get update -qq && apt-get install -y --no-install-recommends mise \
  && rm -rf /var/lib/apt/lists/*

# Trust any mise config under /workspaces without interactive `mise trust`.
ENV MISE_TRUSTED_CONFIG_PATHS=/workspaces

# Source mise-shell-init for interactive terminals; report auth status on TTYs.
RUN printf '%s\n' \
  '[ -r /workspaces/.devcontainer/scripts/shell/mise-shell-init.sh ] && . /workspaces/.devcontainer/scripts/shell/mise-shell-init.sh' \
  '[ -t 0 ] && ensure-auth >/dev/null 2>&1 || true' \
  >> /home/developer/.bashrc

# ------------------------------------------------------------------------------
# AI coding CLI: Gemini CLI.  Run `gemini` in the terminal.
#   - Free tier: run `gemini` and sign in with Google (no API key needed).
#   - Or export GEMINI_API_KEY (https://aistudio.google.com/apikey) for API key auth.
#   - Config/sessions live in ~/.gemini; compose mounts the gemini-data
#     named volume there (and under .devcontainer/persist/gemini).
#   Docs: https://github.com/google-gemini/gemini-cli
# ------------------------------------------------------------------------------
USER developer:developer
RUN npm config set prefix /home/developer/.npm-global && \
    npm install -g @google/gemini-cli

# ------------------------------------------------------------------------------
# AI coding CLI: OpenAI Codex.  Run `codex` in the terminal.
#   - Sign in with a ChatGPT account, or export OPENAI_API_KEY.
#   - Login/config/sessions live in ~/.codex, mounted directly from codex-state.
#   Docs: https://github.com/openai/codex
# ------------------------------------------------------------------------------
RUN npm install -g @openai/codex

# ------------------------------------------------------------------------------
# Cursor agent CLI — register this devcontainer as a My Machines Cloud Agent worker.
#   Docs: https://cursor.com/docs/cloud-agent/my-machines
# ------------------------------------------------------------------------------
# Linux login is in ~/.config/cursor; chats/config are in ~/.cursor.
# Both are backed by named volumes; binaries in ~/.local/share stay image-owned.
RUN curl https://cursor.com/install -fsS | bash
ENV PATH="/home/developer/.npm-global/bin:/home/developer/.local/bin:${PATH}"
USER root

# Google Agent Development Kit and LiteLLM. ADK talks to the local Ollama
# server and to MCP tools. litellm>=1.84 avoids the 1.82.7 and 1.82.8 releases.
RUN apt-get update -qq && apt-get install -y --no-install-recommends python3-venv \
  && python3 -m venv /opt/google-adk \
  && /opt/google-adk/bin/pip install --upgrade pip \
  && /opt/google-adk/bin/pip install "litellm>=1.84" "google-adk[mcp]" \
  && ln -sf /opt/google-adk/bin/adk /usr/local/bin/adk \
  && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# start-vnc: launches Xvfb → XFCE4 → x11vnc → noVNC.
#   Safe to call repeatedly — kills stale processes first.
#   Uses nohup so background processes survive when postStartCommand's shell exits.
# ------------------------------------------------------------------------------
COPY --chmod=0755 .devcontainer/scripts/dockerfile/start-vnc /usr/local/bin/start-vnc


# ensure-auth: report host-forwarded SSH agent + GitHub CLI status (keys stay on the host).
# Passphrase-protected keys: ssh-add once on the host against HOST_SSH_AUTH_SOCK.
COPY --chmod=0755 .devcontainer/scripts/dockerfile/ensure-auth /usr/local/bin/ensure-auth

# print-cursor-worker-hint: quick start for My Machines Cloud Agent workers.
COPY --chmod=0755 .devcontainer/scripts/dockerfile/print-cursor-worker-hint /usr/local/bin/print-cursor-worker-hint

# Ollama client only, same image tag as the local-llm service. `lllm` chats with that
# one server through OLLAMA_HOST. The runners stay in the local-llm container.
COPY --from=ollama/ollama:0.40.8 /usr/bin/ollama /usr/local/bin/ollama
COPY --chmod=0755 .devcontainer/scripts/dockerfile/lllm /usr/local/bin/lllm

USER developer:developer
# ------------------------------------------------------------------------------
# Claude Code CLI: native stable release. Run `claude` and sign in interactively.
# Keep the native binary in ~/.local/share/claude (image-owned), not the state volume.
# Explicit CLAUDE_CONFIG_DIR also puts global .claude.json inside that volume.
# Docs: https://code.claude.com/docs/en/setup
# ------------------------------------------------------------------------------
ENV CLAUDE_CONFIG_DIR=/home/developer/.claude
RUN curl -fsSL https://claude.ai/install.sh -o /tmp/install-claude.sh \
  && bash /tmp/install-claude.sh stable \
  && rm /tmp/install-claude.sh

# Official Linux desktop applications. Cursor uses its published Debian package;
# ChatGPT configures OpenAI's signed update repository during package installation.
# Claude Desktop is installed from Anthropic's signed stable apt repository.
USER root
ARG CURSOR_DESKTOP_VERSION=3.29
RUN case "$TARGETARCH" in amd64) cursor_architecture=x64 ;; arm64) cursor_architecture=arm64 ;; *) echo "Unsupported target architecture: $TARGETARCH" >&2; exit 1 ;; esac \
  && curl -fsSL https://downloads.claude.ai/claude-desktop/key.asc \
      -o /usr/share/keyrings/claude-desktop-archive-keyring.asc \
  && echo "deb [signed-by=/usr/share/keyrings/claude-desktop-archive-keyring.asc] https://downloads.claude.ai/claude-desktop/apt/stable stable main" \
      > /etc/apt/sources.list.d/claude-desktop.list \
  && curl -fsSL "https://api2.cursor.sh/updates/download/golden/linux-${cursor_architecture}-deb/cursor/${CURSOR_DESKTOP_VERSION}" -o /tmp/cursor.deb \
  && curl -fsSL https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_${TARGETARCH}.deb -o /tmp/chatgpt.deb \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends /tmp/cursor.deb /tmp/chatgpt.deb claude-desktop gnome-keyring \
  && rm /tmp/cursor.deb /tmp/chatgpt.deb \
  && rm -rf /var/lib/apt/lists/*

# Create application mount points with the developer's ownership for fresh volumes.
RUN install -d -m 0700 -o developer -g developer \
    /home/developer/.codex \
    /home/developer/.config/Codex \
    /home/developer/.claude \
    /home/developer/.config/Claude \
    /home/developer/.cursor \
    /home/developer/.config/cursor \
    /home/developer/.config/Cursor

# Native desktop secrets are shared through the user's Secret Service keyring.
RUN install -d -m 0700 -o developer -g developer /home/developer/.local/share/keyrings
COPY .devcontainer/desktop/autostart/ /etc/xdg/autostart/

# AI CLI shortcuts for the XFCE desktop and application menu.
COPY .devcontainer/desktop/icons/ /usr/local/share/icons/super-projects/
COPY .devcontainer/desktop/*.desktop /usr/local/share/applications/
COPY --chown=developer:developer --chmod=0755 .devcontainer/desktop/*.desktop /home/developer/Desktop/
# Open the workspace bind mount directly from the desktop file manager.
# Electron apps need software rendering on the virtual desktop (no GPU device).
# Preserve vendor names, icons, actions, and URL handlers while adding this flag.
RUN sed -i -E 's#^Exec=(/usr/share/cursor/cursor|chatgpt|claude-desktop) #Exec=\1 --disable-gpu #' \
      /usr/share/applications/cursor.desktop /usr/share/applications/chatgpt.desktop \
      /usr/share/applications/com.anthropic.Claude.desktop \
  && sed -i 's#^Exec=/usr/share/cursor/cursor --disable-gpu %F#Exec=/usr/share/cursor/cursor --disable-gpu --ozone-platform=x11 --new-window /workspaces %F#' /usr/share/applications/cursor.desktop \
  && install -o developer -g developer -m 0755 \
      /usr/share/applications/cursor.desktop /usr/share/applications/chatgpt.desktop \
      /usr/share/applications/com.anthropic.Claude.desktop /home/developer/Desktop/

# Official VS Code stable package; apt selects the image's target architecture.
# Reuse Microsoft's signing key installed for Azure CLI.
RUN printf 'Types: deb\nURIs: https://packages.microsoft.com/repos/code\nSuites: stable\nComponents: main\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/microsoft.gpg\n' "$TARGETARCH" \
      > /etc/apt/sources.list.d/vscode.sources \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends code \
  && rm -rf /var/lib/apt/lists/*

# Use the package's desktop IDs (current releases use reverse-domain names).
RUN install -d -m 0700 -o developer -g developer \
      /home/developer/.config/Code /home/developer/.config/Code/User \
      /home/developer/.config/Cursor/User /home/developer/.vscode /home/developer/.vscode-server \
      /home/developer/.cursor-server \
  && for desktop_entry in $(dpkg-query -L code | sed -n '\#^/usr/share/applications/.*\.desktop$#p'); do \
      sed -i 's#^Exec=/usr/share/code/code #Exec=/usr/share/code/code --disable-gpu --disable-telemetry --disable-crash-reporter --ozone-platform=x11 #' "$desktop_entry"; \
      if grep -q '^Type=Application' "$desktop_entry" && ! grep -q '^NoDisplay=true' "$desktop_entry"; then \
        sed -i '0,/ %F/s# %F# --new-window /workspaces %F#' "$desktop_entry"; \
        install -o developer -g developer -m 0755 "$desktop_entry" /home/developer/Desktop/; \
      fi; \
    done

# Native Linux GUI is intentional even when the Docker host uses WSL.
ENV DONT_PROMPT_WSL_INSTALL=1
USER developer:developer
# Fresh extension volumes inherit these defaults; user-installed extensions persist.
RUN code --disable-telemetry --install-extension openai.chatgpt

# USER root
# dumb-init is PID 1: properly forwards signals and reaps zombie child processes.
# compose's `command: tail -f /dev/null` becomes `dumb-init -- tail -f /dev/null`.
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bash", "-c", "start-vnc && exec tail -f /dev/null"]

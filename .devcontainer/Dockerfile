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
#   ~250 MB; amd64-only (Google does not publish arm64 Chrome debs).
#   fonts-liberation: core fonts Chrome needs for proper text rendering.
#   A wrapper at /usr/local/bin/chrome applies the container-required flags:
#     --no-sandbox              Chrome cannot create a user namespace sandbox inside Docker.
#     --enable-unsafe-swiftshader  Software WebGL (no GPU in the container).
#     --ignore-gpu-blocklist    Allow SwiftShader when Chrome would blocklist the GPU.
# ------------------------------------------------------------------------------
RUN install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
  && chmod a+r /etc/apt/keyrings/google-chrome.gpg \
  && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
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
# Node.js 20 LTS via NodeSource (Ubuntu ships v18; Gemini CLI requires v20+)
# npm is bundled with the NodeSource nodejs package — no separate install needed.
# ------------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
  && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
  && apt-get update -qq \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

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
# Cursor agent CLI — register this devcontainer as a My Machines Cloud Agent worker.
#   Docs: https://cursor.com/docs/cloud-agent/my-machines
# ------------------------------------------------------------------------------
RUN curl https://cursor.com/install -fsS | bash
ENV PATH="/home/developer/.npm-global/bin:/home/developer/.local/bin:${PATH}"
USER root

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

# ------------------------------------------------------------------------------
# Claude Code CLI (commented out; uncomment and rebuild to enable)
#   Requires ANTHROPIC_API_KEY or a Claude Pro/Max/Console login.
# ------------------------------------------------------------------------------
# RUN apt-get update -qq && apt-get install -y --no-install-recommends jq && rm -rf /var/lib/apt/lists/*
# ARG CLAUDE_GCS_BUCKET=https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases
# RUN set -eux; \
#   ARCH=$(dpkg --print-architecture); \
#   case "$ARCH" in amd64) SUFFIX=x64;; arm64) SUFFIX=arm64;; *) echo "Unsupported arch: $ARCH" >&2; exit 1;; esac; \
#   PLATFORM=linux-$SUFFIX; \
#   VERSION=$(curl -fsSL "$CLAUDE_GCS_BUCKET/latest"); \
#   MANIFEST=$(curl -fsSL "$CLAUDE_GCS_BUCKET/$VERSION/manifest.json"); \
#   CHECKSUM=$(echo "$MANIFEST" | jq -r ".platforms[\"$PLATFORM\"].checksum"); \
#   curl -fsSL "$CLAUDE_GCS_BUCKET/$VERSION/$PLATFORM/claude" -o /tmp/claude; \
#   echo "$CHECKSUM  /tmp/claude" | sha256sum -c -; \
#   chmod 755 /tmp/claude; \
#   mv /tmp/claude /usr/local/bin/claude

USER developer:developer
# USER root
# dumb-init is PID 1: properly forwards signals and reaps zombie child processes.
# compose's `command: tail -f /dev/null` becomes `dumb-init -- tail -f /dev/null`.
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bash", "-c", "start-vnc && exec tail -f /dev/null"]

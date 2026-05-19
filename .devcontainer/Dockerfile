ARG UBUNTU_VERSION=24.04
FROM ubuntu:${UBUNTU_VERSION}

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Install core development tools and mise build dependencies.
# curl:           downloading packages and general HTTP from the terminal
# git:            version control
# openssh-client: share host SSH credentials (needed for git operations over SSH)
# vim:            quick terminal edits when SSH'd in
# procps:         top, free, ps — system monitoring
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
# Pre-create the chrome-profile dir so Docker initialises the named volume with
# developer ownership (Docker creates missing volume mount points as root).
RUN chown -R developer:developer /home/developer && \
    mkdir -p /home/developer/chrome-profile && \
    chown developer:developer /home/developer/chrome-profile

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
    CHROME_REMOTE_DEBUGGING_PORT=9223

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
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
#     --no-sandbox       Chrome cannot create a user namespace sandbox inside Docker.
#     --disable-gpu      No real GPU in the container; avoids slow GPU probe loops.
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
RUN printf '#!/bin/bash\n\
CHROME_PORT="${CHROME_REMOTE_DEBUGGING_PORT:-9223}"\n\
_profile="${CHROME_USER_DATA_DIR:-/home/developer/chrome-profile}"\n\
\n\
_chrome_ready() {\n\
  curl -sf --max-time 1 "http://localhost:${CHROME_PORT}/json/version" >/dev/null 2>&1\n\
}\n\
\n\
if ! _chrome_ready; then\n\
  chown -R "$(id -u):$(id -g)" "$_profile" 2>/dev/null || true\n\
  rm -f "$_profile/SingletonLock" "$_profile/SingletonSocket" "$_profile/SingletonCookie" 2>/dev/null\n\
  nohup env DISPLAY="${DISPLAY:-:99}" /usr/bin/google-chrome \\\n\
    --no-sandbox \\\n\
    --disable-gpu \\\n\
    --remote-debugging-port="${CHROME_PORT}" \\\n\
    --remote-debugging-address=0.0.0.0 \\\n\
    --remote-allow-origins="*" \\\n\
    --user-data-dir="$_profile" \\\n\
    "${@:-about:blank}" >/tmp/chrome.log 2>&1 &\n\
  for i in $(seq 20); do\n\
    _chrome_ready && break\n\
    sleep 0.5\n\
  done\n\
  _chrome_ready || echo "Chrome may have failed to start; check /tmp/chrome.log" >&2\n\
fi\n\
' > /usr/local/bin/chrome && chmod +x /usr/local/bin/chrome

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

# ------------------------------------------------------------------------------
# AI coding CLI: Gemini CLI.  Run `gemini` in the terminal.
#   - Free tier: run `gemini` and sign in with Google (no API key needed).
#   - Or export GEMINI_API_KEY (https://aistudio.google.com/apikey) for API key auth.
#   - Config/sessions live in ~/.gemini; compose bind-mounts
#     .devcontainer/gemini-data there so data persists across rebuilds.
#   Docs: https://github.com/google-gemini/gemini-cli
# ------------------------------------------------------------------------------
USER developer:developer
# mise shims first so mise-managed tools shadow system ones; npm-global bin follows.
# MISE_TRUSTED_CONFIG_PATHS pre-trusts /workspaces and all subdirectories so mise
# reads each project's .mise.toml without prompting for `mise trust`.
ENV PATH="/home/developer/.local/share/mise/shims:/home/developer/.npm-global/bin:${PATH}" \
    MISE_TRUSTED_CONFIG_PATHS=/workspaces
RUN mkdir -p /home/developer/.config/mise
RUN npm config set prefix /home/developer/.npm-global && \
    npm install -g @google/gemini-cli
USER root

# ==============================================================================
# BUILD-TIME TOOL INSTALLATION (optional — uncomment to bake versions into image)
# ==============================================================================
# If you maintain a .mise.toml at the workspace root, you can have mise install
# the exact tool versions at image build time so every developer gets them
# pre-cached without waiting on first-run downloads.
#
# 1. Uncomment the two lines below.
# 2. Rebuild the image (`devcontainer up --remove-existing-container`).
#    The COPY line will only bust the cache when .mise.toml actually changes,
#    so normal Dockerfile edits above this point stay fully cached.
#
# COPY --chown=developer:developer ../.mise.toml /workspaces/.mise.toml
# RUN cd /workspaces && mise trust && mise install

# ------------------------------------------------------------------------------
# start-vnc: launches Xvfb → XFCE4 → x11vnc → noVNC.
#   Safe to call repeatedly — kills stale processes first.
#   Uses nohup so background processes survive when postStartCommand's shell exits.
# ------------------------------------------------------------------------------
RUN printf '#!/bin/bash\n\
pkill Xvfb 2>/dev/null\n\
pkill x11vnc 2>/dev/null\n\
pkill websockify 2>/dev/null\n\
pkill -f xfce4-session 2>/dev/null\n\
pkill -f google-chrome 2>/dev/null\n\
sleep 0.3\n\
nohup Xvfb :99 -screen 0 "${NOVNC_RESOLUTION:-1920x1080}x24" >/tmp/xvfb.log 2>&1 &\n\
sleep 0.5\n\
nohup env DISPLAY=:99 startxfce4 >/tmp/xfce4.log 2>&1 &\n\
setsid x11vnc -display :99 -nopw -forever -shared \\\n\
  -rfbport "${VNC_PORT:-5900}" >/tmp/x11vnc.log 2>&1 &\n\
sleep 0.5\n\
nohup websockify --web /usr/share/novnc \\\n\
  "${NOVNC_PORT:-6080}" "localhost:${VNC_PORT:-5900}" >/tmp/websockify.log 2>&1 &\n\
chrome\n\
echo "noVNC ready:  http://localhost:${NOVNC_PORT:-6080}/vnc.html"\n\
echo "Chrome DevTools: http://localhost:${CHROME_REMOTE_DEBUGGING_PORT:-9223}"\n\
' > /usr/local/bin/start-vnc && chmod +x /usr/local/bin/start-vnc

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

WORKDIR /workspaces

# Start new shells in /workspaces; activate mise so interactive terminals pick up
# mise-managed tools automatically (shims handle non-interactive scripts via PATH).
RUN echo 'cd /workspaces' >> /home/developer/.bashrc && \
    echo 'eval "$(mise activate bash)"' >> /home/developer/.bashrc

USER developer:developer

# dumb-init is PID 1: properly forwards signals and reaps zombie child processes.
# compose's `command: tail -f /dev/null` becomes `dumb-init -- tail -f /dev/null`.
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["start-vnc", "&&", "tail", "-f", "/dev/null"]

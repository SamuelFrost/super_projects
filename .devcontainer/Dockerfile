ARG UBUNTU_VERSION=24.04
FROM ubuntu:${UBUNTU_VERSION}

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Install core development tools
# curl:           downloading packages and general HTTP from the terminal
# git:            version control
# openssh-client: share host SSH credentials (needed for git operations over SSH)
# vim:            quick terminal edits when SSH'd in
# procps:         top, free, ps — system monitoring
# poppler-utils:  pdftotext etc. — lets agents/scripts read PDFs as text
# ffmpeg:         probe/process video and audio (metadata, extract audio)
# zlib1g-dev:     common compression library required by several build tools
# tzdata:         timezone data (suppressed interactive prompt via ENV above)
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
  curl \
  git \
  openssh-client \
  vim \
  procps \
  poppler-utils \
  ffmpeg \
  zlib1g-dev \
  tzdata \
  ca-certificates \
  gnupg \
  && rm -rf /var/lib/apt/lists/*

# Build args: populated by initializeCommand with host `id -u` and `docker.sock` gid
ARG DEVELOPER_UID=501
ARG DOCKER_GID=1

# Create docker group with the host's GID so the mounted docker.sock is accessible
RUN groupadd --gid ${DOCKER_GID} docker || groupadd --gid 1001 docker || groupadd docker || true

# Create developer user matching the host UID (updateRemoteUserUID in devcontainer.json can adjust UID at start)
RUN groupadd --system developer && \
  useradd --system --uid ${DEVELOPER_UID} --gid developer --create-home --shell /bin/bash developer && \
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
  && curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
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
    CHROME_REMOTE_DEBUGGING_PORT=9223 \
    MCP_PROXY_PORT=8080

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
       pipx \
  && rm -rf /var/lib/apt/lists/*

# Wrapper so any launch path (terminal, desktop, start-vnc) gets the full set
# of required flags without repetition. Reads ENV vars so values are tuneable
# via `docker compose environment:` without rebuilding.
RUN printf '#!/bin/bash\n\
# Clear stale singleton lock files so a second invocation (e.g. from the\n\
# terminal while start-vnc already launched Chrome, or after a container\n\
# restart) never hits the "profile in use by another computer" error.\n\
_profile="${CHROME_USER_DATA_DIR:-/home/developer/chrome-profile}"\n\
rm -f "$_profile/SingletonLock" "$_profile/SingletonSocket" "$_profile/SingletonCookie" 2>/dev/null\n\
exec /usr/bin/google-chrome \\\n\
  --no-sandbox \\\n\
  --disable-gpu \\\n\
  --remote-debugging-port="${CHROME_REMOTE_DEBUGGING_PORT:-9223}" \\\n\
  --remote-debugging-address=127.0.0.1 \\\n\
  --user-data-dir="$_profile" \\\n\
  "$@"\n' \
  > /usr/local/bin/chrome && chmod +x /usr/local/bin/chrome

# Point the XFCE application menu launcher at the wrapper so it also picks up
# all the flags above (including remote-debugging-port for MCP connectivity).
RUN sed -i \
  's|Exec=/usr/bin/google-chrome-stable|Exec=/usr/local/bin/chrome|g' \
  /usr/share/applications/google-chrome.desktop

# ------------------------------------------------------------------------------
# mcp-proxy — HTTP/WebSocket gateway that wraps stdio MCP servers.
#   Installed system-wide via pipx so it is reachable by any user.
#   PIPX_BIN_DIR=/usr/local/bin puts the `mcp-proxy` binary on the global PATH.
#   Docs: https://github.com/sparfenyuk/mcp-proxy
# ------------------------------------------------------------------------------
ENV PIPX_HOME=/opt/pipx \
    PIPX_BIN_DIR=/usr/local/bin
RUN pipx install mcp-proxy

# ==============================================================================
# LIGHTER / MORE FREQUENTLY UPDATED LAYERS
# ==============================================================================

# ------------------------------------------------------------------------------
# Node.js 20 LTS via NodeSource (Ubuntu ships v18; chrome-devtools-mcp requires v20+)
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
# AI coding CLI: Gemini CLI.  Run `gemini` in the terminal.
#   - Free tier: run `gemini` and sign in with Google (no API key needed).
#   - Or export GEMINI_API_KEY (https://aistudio.google.com/apikey) for API key auth.
#   - Config/sessions live in ~/.gemini; compose bind-mounts
#     .devcontainer/gemini-data there so data persists across rebuilds.
#   Docs: https://github.com/google-gemini/gemini-cli
# ------------------------------------------------------------------------------
USER developer:developer
# Put developer's npm global bin on PATH so globally installed packages are reachable by name
ENV PATH="/home/developer/.npm-global/bin:${PATH}"
# Puppeteer bundled with chrome-devtools-mcp would download its own Chrome; skip it since we have Chrome installed.
ENV PUPPETEER_SKIP_DOWNLOAD=true
RUN npm config set prefix /home/developer/.npm-global && \
    npm install -g @google/gemini-cli && \
    npm install -g chrome-devtools-mcp
USER root

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
pkill mcp-proxy 2>/dev/null\n\
sleep 0.3\n\
nohup Xvfb :99 -screen 0 "${NOVNC_RESOLUTION:-1920x1080}x24" >/tmp/xvfb.log 2>&1 &\n\
sleep 0.5\n\
nohup env DISPLAY=:99 startxfce4 >/tmp/xfce4.log 2>&1 &\n\
setsid x11vnc -display :99 -nopw -forever -shared \\\n\
  -rfbport "${VNC_PORT:-5900}" >/tmp/x11vnc.log 2>&1 &\n\
sleep 0.5\n\
nohup websockify --web /usr/share/novnc \\\n\
  "${NOVNC_PORT:-6080}" "localhost:${VNC_PORT:-5900}" >/tmp/websockify.log 2>&1 &\n\
nohup env DISPLAY=:99 chrome chrome://inspect/#remote-debugging >/tmp/chrome.log 2>&1 &\n\
sleep 1\n\
nohup mcp-proxy --port "${MCP_PROXY_PORT:-8080}" -- \\\n\
  chrome-devtools-mcp \\\n\
  --browser-url "http://localhost:${CHROME_REMOTE_DEBUGGING_PORT:-9223}" \\\n\
  >/tmp/mcp-proxy.log 2>&1 &\n\
echo "noVNC ready:  http://localhost:${NOVNC_PORT:-6080}/vnc.html"\n\
echo "MCP proxy:    http://localhost:${MCP_PROXY_PORT:-8080}/mcp"\n\
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

# Start new shells in /workspaces instead of $HOME
RUN echo 'cd /workspaces' >> /home/developer/.bashrc

USER developer:developer

# dumb-init is PID 1: properly forwards signals and reaps zombie child processes.
# compose's `command: tail -f /dev/null` becomes `dumb-init -- tail -f /dev/null`.
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["start-vnc", "&&", "tail", "-f", "/dev/null"]

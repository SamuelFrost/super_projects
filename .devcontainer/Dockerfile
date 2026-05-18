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

# Ensure developer owns their home directory
RUN chown -R developer:developer /home/developer

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

# ------------------------------------------------------------------------------
# Node.js + npm  (required for Gemini CLI and other JS-based tooling)
# ------------------------------------------------------------------------------
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
  nodejs \
  npm \
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
RUN npm config set prefix /home/developer/.npm-global && npm install -g @google/gemini-cli
USER root

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

CMD ["tail", "-f", "/dev/null"]

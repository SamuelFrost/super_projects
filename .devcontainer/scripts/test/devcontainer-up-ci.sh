#!/bin/sh
# CI test: official `devcontainer up` path (initializeCommand → compose build/start → exec).
# Intended for a standalone Docker host (GitHub-hosted ubuntu-latest).
#
# Not run in CI:
# - macOS: GitHub-hosted macOS runners cannot run Docker Desktop/Colima
# - Nested meta-dev: compose project name `super_projects` would collide with the outer container
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
cd "$REPO_ROOT"

HOST_OS=$(uname -s)
COMPOSE_FILE=.devcontainer/compose.yaml
STARTED_UP=0

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

is_nested_devcontainer() {
  [ -f /.dockerenv ] && [ -f ../.devcontainer/compose.yaml ]
}

compose_project_has_containers() {
  _ids=$(docker compose -f "$COMPOSE_FILE" ps -aq 2>/dev/null) || _ids=
  [ -n "$_ids" ]
}

if is_nested_devcontainer; then
  log "skip: nested devcontainer (compose project name would collide with the outer environment)"
  exit 0
fi

command -v docker >/dev/null 2>&1 || fail "docker not found (required for devcontainer up)"
docker info >/dev/null 2>&1 || fail "docker daemon is not reachable"
command -v devcontainer >/dev/null 2>&1 || fail "devcontainer CLI not found (install @devcontainers/cli)"

if [ -z "${GITHUB_ACTIONS:-}" ] && compose_project_has_containers; then
  log "skip: compose project already has containers (refusing to replace a local super_projects stack)"
  exit 0
fi

ENV_BACKUP_DIR=$(mktemp -d /tmp/spci-env-XXXXXX)
ENV_HAD_DOTENV=0
ENV_HAD_SELECTED=0
ENV_HAD_LEGACY=0
if [ -f .devcontainer/.env ]; then
  cp .devcontainer/.env "$ENV_BACKUP_DIR/.env"
  ENV_HAD_DOTENV=1
fi
if [ -f .devcontainer/.selected-ssh-agent.env ]; then
  cp .devcontainer/.selected-ssh-agent.env "$ENV_BACKUP_DIR/.selected-ssh-agent.env"
  ENV_HAD_SELECTED=1
fi
if [ -f .devcontainer/.host-ssh-agent.env ]; then
  cp .devcontainer/.host-ssh-agent.env "$ENV_BACKUP_DIR/.host-ssh-agent.env"
  ENV_HAD_LEGACY=1
fi

# Isolated HOME so runner ssh state does not affect results. Keep paths short:
# macOS limits Unix socket paths to 104 bytes; use /tmp/spci-XXXXXX, not $TMPDIR mktemp.
TEST_HOME=$(mktemp -d /tmp/spci-XXXXXX)
export HOME="$TEST_HOME"
export XDG_RUNTIME_DIR="$HOME/.cache"
mkdir -p "$HOME/.ssh" "$XDG_RUNTIME_DIR"
unset SSH_AUTH_SOCK

restore_generated_env_files() {
  if [ "$ENV_HAD_DOTENV" -eq 1 ]; then
    cp "$ENV_BACKUP_DIR/.env" .devcontainer/.env
  else
    rm -f .devcontainer/.env
  fi
  if [ "$ENV_HAD_SELECTED" -eq 1 ]; then
    cp "$ENV_BACKUP_DIR/.selected-ssh-agent.env" .devcontainer/.selected-ssh-agent.env
  else
    rm -f .devcontainer/.selected-ssh-agent.env
  fi
  if [ "$ENV_HAD_LEGACY" -eq 1 ]; then
    cp "$ENV_BACKUP_DIR/.host-ssh-agent.env" .devcontainer/.host-ssh-agent.env
  else
    rm -f .devcontainer/.host-ssh-agent.env
  fi
}

kill_agent_at_socket() {
  _sock=$1
  [ -n "$_sock" ] || return 0
  [ -e "$_sock" ] || return 0
  if [ "$HOST_OS" = Darwin ]; then
    _pids=$(lsof -t -U "$_sock" 2>/dev/null) || _pids=
  else
    _pids=$(fuser "$_sock" 2>/dev/null) || _pids=
  fi
  for _pid in $_pids; do
    kill "$_pid" 2>/dev/null || true
  done
  rm -f "$_sock"
}

cleanup() {
  _status=$?

  if [ "$STARTED_UP" -eq 1 ] || compose_project_has_containers; then
    log "tearing down compose project"
    docker compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
  fi

  kill_agent_at_socket "${XDG_RUNTIME_DIR:-}/super_projects-ssh-agent.sock"
  restore_generated_env_files
  rm -rf "$TEST_HOME" "$ENV_BACKUP_DIR"

  exit "$_status"
}

trap cleanup EXIT INT TERM

log "phase: generate unencrypted default SSH key in isolated HOME"
ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q

HOST_UID=$(id -u)

log "phase: devcontainer up --remove-existing-container"
if ! devcontainer up --workspace-folder "$REPO_ROOT" --remove-existing-container; then
  log "compose logs (tail)"
  docker compose -f "$COMPOSE_FILE" logs --tail=200 || true
  fail "devcontainer up failed"
fi
STARTED_UP=1

run_in_container() {
  devcontainer exec --workspace-folder "$REPO_ROOT" sh -c "$1"
}

log "phase: assert container contracts"
run_in_container 'test "$(whoami)" = developer' || fail "expected user developer"
run_in_container "test \"\$(id -u)\" = \"$HOST_UID\"" || fail "container uid does not match host uid $HOST_UID"
run_in_container 'test -f /workspaces/README.md' || fail "workspace README.md not mounted at /workspaces"
run_in_container 'test -f /workspaces/.devcontainer/devcontainer.json' || fail "devcontainer.json not mounted at /workspaces"
run_in_container 'test -S /ssh-agent.sock' || fail "host ssh-agent socket not forwarded at /ssh-agent.sock"
run_in_container 'test "${SSH_AUTH_SOCK:-}" = /ssh-agent.sock' || fail "SSH_AUTH_SOCK is not /ssh-agent.sock"
run_in_container 'ssh-add -l | grep -qi ed25519' || fail "forwarded ssh-agent does not list the test ed25519 key"
run_in_container 'test -S /var/run/docker.sock' || fail "docker.sock is not mounted"
run_in_container 'docker info >/dev/null' || fail "docker.sock is not usable from inside the container"

log "devcontainer up CI passed on $HOST_OS"

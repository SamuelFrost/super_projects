#!/bin/sh
# CI tests for host initializeCommand flow (ensure-host-ssh-agent + write-devcontainer-env).
# Run on native Linux and macOS GitHub Actions runners.
#
# assert_env_contract also checks DEVELOPER_UID/DOCKER_GID, bridge↔.env socket parity
# (standalone hosts), legacy bridge removal, and compose config with generated .env.
# assert_initialize_command_artifacts checks persist/ stubs and known_hosts (standalone).
# Limitations (not run in CI):
# - macOS Keychain UI unlock (no-TTY Darwin branch) — requires manual IDE verification
# - Interactive TTY passphrase prompt — use Linux askpass test as the IDE-like proxy
# - Nested devcontainer path resolution — covered locally; unlock tests require a standalone host
# - macOS compose/.env generation — GitHub-hosted macOS runners cannot run Colima/Docker Desktop
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
cd "$REPO_ROOT"

UNLOCK_MODE=${1:-all}
HOST_OS=$(uname -s)

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
mkdir -p "$HOME/.ssh" "$XDG_RUNTIME_DIR" "$HOME/bin"

AGENT_PIDS=
AGENT_SOCKS=

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

env_var() {
  _file=$1
  _key=$2
  grep -m1 "^${_key}=" "$_file" | cut -d= -f2-
}

kill_agent_at_socket() {
  _sock=$1
  [ -n "$_sock" ] || return 0

  _pids=$(pgrep -f "ssh-agent -a $_sock" 2>/dev/null) || _pids=
  if [ -z "$_pids" ] && [ -e "$_sock" ]; then
    if [ "$HOST_OS" = Darwin ]; then
      _pids=$(lsof -t -U "$_sock" 2>/dev/null) || _pids=
    else
      _pids=$(fuser "$_sock" 2>/dev/null) || _pids=
    fi
  fi
  for _pid in $_pids; do
    kill "$_pid" 2>/dev/null || true
  done
  rm -f "$_sock"
}

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

cleanup() {
  _status=$?

  for _pid in $AGENT_PIDS; do
    [ -n "$_pid" ] && kill "$_pid" 2>/dev/null || true
  done
  for _sock in $AGENT_SOCKS "$HOME/.cache/super_projects-ssh-agent.sock" "$HOME/preloaded-agent.sock"; do
    kill_agent_at_socket "$_sock"
  done

  restore_generated_env_files
  rm -rf "$TEST_HOME" "$ENV_BACKUP_DIR"

  exit "$_status"
}

trap cleanup EXIT INT TERM

register_agent_pid() {
  _pid=$1
  [ -n "$_pid" ] || return 0
  AGENT_PIDS="$AGENT_PIDS $_pid"
}

register_agent_socket() {
  _sock=$1
  [ -n "$_sock" ] || return 0
  AGENT_SOCKS="$AGENT_SOCKS $_sock"
}

start_test_agent() {
  _sock=$1
  eval "$(ssh-agent -a "$_sock" -s)"
  register_agent_pid "$SSH_AGENT_PID"
  register_agent_socket "$_sock"
  export SSH_AUTH_SOCK="$_sock"
}

is_nested_devcontainer() {
  [ -f /.dockerenv ] && [ -f ../.devcontainer/compose.yaml ]
}

reset_init_state() {
  rm -f .devcontainer/.env .devcontainer/.selected-ssh-agent.env .devcontainer/.host-ssh-agent.env
  rm -rf "$HOME/.cache/super_projects-ssh-agent.sock" "$XDG_RUNTIME_DIR/super_projects-ssh-agent.sock"
  find "$HOME" -maxdepth 1 -name '*.sock' -exec rm -rf {} + 2>/dev/null || true
  rm -f "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_ed25519.pub" \
    "$HOME/.ssh/id_rsa" "$HOME/.ssh/id_rsa.pub" \
    "$HOME/.ssh/id_ecdsa" "$HOME/.ssh/id_ecdsa.pub"
  unset SSH_AUTH_SOCK
}

generate_ed25519_key() {
  _key=$1
  _pass=$2
  rm -f "$_key" "${_key}.pub"
  if [ -n "$_pass" ]; then
    ssh-keygen -t ed25519 -N "$_pass" -f "$_key" -q
  else
    ssh-keygen -t ed25519 -N "" -f "$_key" -q
  fi
}

require_docker() {
  command -v docker >/dev/null 2>&1 || fail "docker not found (required for compose config and .env generation)"
}

docker_sock_gid() {
  if [ "$HOST_OS" = Darwin ]; then
    stat -f '%g' /var/run/docker.sock
  else
    stat -c '%g' /var/run/docker.sock
  fi
}

register_selected_agent_from_bridge() {
  if [ -f .devcontainer/.selected-ssh-agent.env ]; then
    _sock=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK) || _sock=
    register_agent_socket "$_sock"
  fi
}

assert_env_contract() {
  _env_file=.devcontainer/.env
  [ -f "$_env_file" ] || fail "missing $_env_file"
  [ -f .devcontainer/.selected-ssh-agent.env ] || fail "missing .devcontainer/.selected-ssh-agent.env"

  for _key in DEVELOPER_UID DOCKER_GID HOST_HOME_DIR HOST_SSH_AUTH_SOCK HOST_WORKSPACE_DIR; do
    _value=$(env_var "$_env_file" "$_key") || fail "$_key missing from $_env_file"
    [ -n "$_value" ] || fail "$_key is empty in $_env_file"
  done

  _workspace=$(env_var "$_env_file" HOST_WORKSPACE_DIR)
  case "$_workspace" in
    /*) ;;
    *) fail "HOST_WORKSPACE_DIR must be absolute: $_workspace" ;;
  esac

  if is_nested_devcontainer; then
    _parent_ws=$(env_var ../.devcontainer/.env HOST_WORKSPACE_DIR) || fail "missing parent HOST_WORKSPACE_DIR"
    case "$_workspace" in
      "$_parent_ws"/*) ;;
      *) fail "nested HOST_WORKSPACE_DIR=$_workspace not under parent $_parent_ws" ;;
    esac
    [ "$(basename "$_workspace")" = "$(basename "$REPO_ROOT")" ] || fail "nested HOST_WORKSPACE_DIR should end with $(basename "$REPO_ROOT")"
  else
    [ "$_workspace" = "$REPO_ROOT" ] || fail "HOST_WORKSPACE_DIR=$_workspace expected $REPO_ROOT"
  fi

  _home=$(env_var "$_env_file" HOST_HOME_DIR)
  if is_nested_devcontainer; then
    _parent_home=$(env_var ../.devcontainer/.env HOST_HOME_DIR) || fail "missing parent HOST_HOME_DIR"
    [ "$_home" = "$_parent_home" ] || fail "nested HOST_HOME_DIR=$_home expected $_parent_home"
  else
    [ "$_home" = "$HOME" ] || fail "HOST_HOME_DIR=$_home expected $HOME"
  fi

  _uid=$(env_var "$_env_file" DEVELOPER_UID)
  [ "$_uid" = "$(id -u)" ] || fail "DEVELOPER_UID=$_uid expected $(id -u)"

  if command -v docker >/dev/null 2>&1 && [ -e /var/run/docker.sock ]; then
    _gid=$(env_var "$_env_file" DOCKER_GID)
    _expected_gid=$(docker_sock_gid)
    [ "$_gid" = "$_expected_gid" ] || fail "DOCKER_GID=$_gid expected $_expected_gid from /var/run/docker.sock"
  fi

  _sock=$(env_var "$_env_file" HOST_SSH_AUTH_SOCK)
  _selected=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK) || fail "SELECTED_AGENT_SOCK missing from bridge file"
  if is_nested_devcontainer; then
    _parent_sock=$(env_var ../.devcontainer/.env HOST_SSH_AUTH_SOCK) || fail "missing parent HOST_SSH_AUTH_SOCK"
    [ "$_sock" = "$_parent_sock" ] || fail "nested HOST_SSH_AUTH_SOCK=$_sock expected $_parent_sock"
  else
    [ -S "$_sock" ] || fail "HOST_SSH_AUTH_SOCK is not a socket: $_sock"
    [ "$_sock" = "$_selected" ] || fail "HOST_SSH_AUTH_SOCK=$_sock expected SELECTED_AGENT_SOCK=$_selected"
  fi

  [ ! -f .devcontainer/.host-ssh-agent.env ] || fail "legacy .devcontainer/.host-ssh-agent.env should be removed"

  if command -v docker >/dev/null 2>&1; then
    docker compose -f .devcontainer/compose.yaml config >/dev/null \
      || fail "docker compose config failed with generated .devcontainer/.env"
  fi
}

assert_initialize_command_artifacts() {
  for _dir in gemini gh git mise chrome cursor; do
    [ -d ".devcontainer/persist/$_dir" ] || fail "missing .devcontainer/persist/$_dir after initializeCommand"
  done

  if ! is_nested_devcontainer; then
    [ -f "$HOME/.ssh/known_hosts" ] || fail "missing $HOME/.ssh/known_hosts after initializeCommand"
  fi
}

phase_compose_without_env() {
  log "phase: compose config without .devcontainer/.env"
  require_docker
  reset_init_state
  docker compose -f .devcontainer/compose.yaml config >/dev/null
}

phase_initialize_contract() {
  log "phase: initializeCommand writes bridge + compose .env"
  reset_init_state
  unset SSH_AUTH_SOCK
  sh .devcontainer/scripts/shell/initializeCommand.sh
  register_selected_agent_from_bridge
  assert_env_contract
  assert_initialize_command_artifacts
}

phase_reuse_loaded_agent() {
  if is_nested_devcontainer; then
    log "skip: reuse preloaded agent (requires standalone Docker host)"
    return 0
  fi

  log "phase: reuse host agent that already has identities"
  reset_init_state

  _key="$HOME/.ssh/id_ed25519"
  generate_ed25519_key "$_key" ""
  _agent_sock="$HOME/preloaded-agent.sock"
  start_test_agent "$_agent_sock"
  ssh-add "$_key" >/dev/null

  sh .devcontainer/scripts/shell/ensure-host-ssh-agent
  register_selected_agent_from_bridge

  _selected=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK)
  [ "$_selected" = "$_agent_sock" ] || fail "expected reuse of preloaded agent (got $_selected)"
  SSH_AUTH_SOCK="$_selected" ssh-add -l | grep -qi ed25519 || fail "preloaded key missing from selected agent"

  if [ "${AGENT_ONLY_TESTS:-0}" = 1 ]; then
    return 0
  fi

  sh .devcontainer/scripts/shell/write-devcontainer-env
  assert_env_contract
}

phase_passphrase_unlock_linux_askpass() {
  if is_nested_devcontainer; then
    log "skip: Linux askpass unlock (requires standalone Docker host)"
    return 0
  fi

  log "phase: passphrase unlock via askpass (non-TTY Linux / IDE-like)"
  [ "$HOST_OS" != Darwin ] || {
    log "skip: Linux askpass path on macOS"
    return 0
  }

  reset_init_state
  unset SSH_AUTH_SOCK

  _pass=ci-test-passphrase
  _key="$HOME/.ssh/id_ed25519"
  generate_ed25519_key "$_key" "$_pass"

  cat >"$HOME/bin/ssh-askpass" <<EOF
#!/bin/sh
echo "$_pass"
EOF
  chmod +x "$HOME/bin/ssh-askpass"
  export PATH="$HOME/bin:$PATH"
  export DISPLAY=:1

  sh .devcontainer/scripts/shell/ensure-host-ssh-agent
  register_selected_agent_from_bridge
  sh .devcontainer/scripts/shell/write-devcontainer-env

  _sock=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK)
  SSH_AUTH_SOCK="$_sock" ssh-add -l | grep -qi ed25519 || fail "passphrase key not loaded after askpass unlock"
  assert_env_contract
}

phase_passphrase_quiet_load() {
  if is_nested_devcontainer; then
    log "skip: quiet load (requires standalone Docker host)"
    return 0
  fi

  log "phase: non-interactive load of unencrypted default key"
  reset_init_state
  unset SSH_AUTH_SOCK

  _key="$HOME/.ssh/id_ed25519"
  generate_ed25519_key "$_key" ""

  sh .devcontainer/scripts/shell/ensure-host-ssh-agent
  register_selected_agent_from_bridge
  if [ "${AGENT_ONLY_TESTS:-0}" = 1 ]; then
    _sock=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK)
    SSH_AUTH_SOCK="$_sock" ssh-add -l | grep -qi ed25519 || fail "unencrypted default key not loaded"
    return 0
  fi

  sh .devcontainer/scripts/shell/write-devcontainer-env

  _sock=$(env_var .devcontainer/.selected-ssh-agent.env SELECTED_AGENT_SOCK)
  SSH_AUTH_SOCK="$_sock" ssh-add -l | grep -qi ed25519 || fail "unencrypted default key not loaded"
  assert_env_contract
}

run_all() {
  phase_compose_without_env
  phase_initialize_contract
  phase_reuse_loaded_agent
  phase_passphrase_unlock_linux_askpass
  phase_passphrase_quiet_load
}

case "$UNLOCK_MODE" in
  all) run_all ;;
  askpass)
    phase_compose_without_env
    phase_initialize_contract
    phase_reuse_loaded_agent
    phase_passphrase_unlock_linux_askpass
    phase_passphrase_quiet_load
    ;;
  quiet)
    phase_compose_without_env
    phase_initialize_contract
    phase_reuse_loaded_agent
    phase_passphrase_quiet_load
    ;;
  macos-agent)
    AGENT_ONLY_TESTS=1
    export AGENT_ONLY_TESTS
    phase_reuse_loaded_agent
    phase_passphrase_quiet_load
    ;;
  *)
    fail "unknown unlock mode: $UNLOCK_MODE (expected all, askpass, quiet, or macos-agent)"
    ;;
esac

log "all requested host initialize CI phases passed on $HOST_OS"

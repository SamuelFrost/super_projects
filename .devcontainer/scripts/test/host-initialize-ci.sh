#!/bin/sh
# CI tests for host initializeCommand flow (ensure-host-ssh-agent + write-devcontainer-env).
# Run on native Linux and macOS GitHub Actions runners.
#
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

# Isolated HOME so runner ssh state does not affect results. Keep paths short:
# macOS limits Unix socket paths to 104 bytes, and mktemp under /var/folders can exceed that.
export HOME="/tmp/spci-$$"
export XDG_RUNTIME_DIR="$HOME/.cache"
mkdir -p "$HOME/.ssh" "$XDG_RUNTIME_DIR" "$HOME/bin"

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

  _sock=$(env_var "$_env_file" HOST_SSH_AUTH_SOCK)
  if is_nested_devcontainer; then
    _parent_sock=$(env_var ../.devcontainer/.env HOST_SSH_AUTH_SOCK) || fail "missing parent HOST_SSH_AUTH_SOCK"
    [ "$_sock" = "$_parent_sock" ] || fail "nested HOST_SSH_AUTH_SOCK=$_sock expected $_parent_sock"
  else
    [ -S "$_sock" ] || fail "HOST_SSH_AUTH_SOCK is not a socket: $_sock"
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
  assert_env_contract
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
  ssh-agent -a "$_agent_sock" >/dev/null
  export SSH_AUTH_SOCK="$_agent_sock"
  ssh-add "$_key" >/dev/null

  sh .devcontainer/scripts/shell/ensure-host-ssh-agent

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

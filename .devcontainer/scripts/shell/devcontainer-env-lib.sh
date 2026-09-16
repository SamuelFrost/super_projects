# Sourced by host initialize scripts (not executed). Callers must cd to the
# repository root first. Paths below are relative to that root.
#
# Shared .env parsers: strip Windows CRLF; override tokens are validated
# separately because bind-mount values (e.g. 1Password sockets) may contain spaces.

NAMESPACE_OVERRIDE_FILE=.devcontainer/.env.namespace_override
DEFAULT_SUPER_PROJECTS_NAME=super_projects
DEFAULT_SUPER_PROJECTS_WORKDIR=workspaces

env_file_var() {
  _file=$1
  _key=$2
  [ -f "$_file" ] || return 1
  _line=$(grep -m1 "^${_key}=" "$_file") || return 1
  _value=${_line#*=}
  _value=$(printf '%s' "$_value" | tr -d '\r')
  printf '%s' "$_value"
}

# Bare assignment token: no quotes, spaces, or export prefix; [a-z0-9][a-z0-9_-]*
validate_override_token() {
  _label=$1
  _value=$2
  case "$_value" in
    '')
      echo "devcontainer env: $_label must not be empty" >&2
      return 1
      ;;
    *\"*|*"'"*)
      echo "devcontainer env: $_label must not be quoted" >&2
      return 1
      ;;
    *[[:space:]]*)
      echo "devcontainer env: $_label must not contain spaces" >&2
      return 1
      ;;
    export\ *)
      echo "devcontainer env: $_label must not use an export prefix" >&2
      return 1
      ;;
  esac
  if ! printf '%s' "$_value" | grep -Eq '^[a-z0-9][a-z0-9_-]*$'; then
    echo "devcontainer env: $_label must match [a-z0-9][a-z0-9_-]* (got: $_value)" >&2
    return 1
  fi
}

# Prints the resolved token. Reads the override when present; otherwise the default.
# Invalid values fail (do not start a misnamed project or mis-mounted workspace).
resolve_override_token() {
  _key=$1
  _default=$2
  _value=$_default
  if [ -f "$NAMESPACE_OVERRIDE_FILE" ]; then
    if grep -q "^export ${_key}=" "$NAMESPACE_OVERRIDE_FILE"; then
      echo "devcontainer env: $NAMESPACE_OVERRIDE_FILE must use ${_key}=... not export ${_key}=" >&2
      return 1
    fi
    if grep -q "^${_key}=" "$NAMESPACE_OVERRIDE_FILE"; then
      _value=$(env_file_var "$NAMESPACE_OVERRIDE_FILE" "$_key") || _value=
    fi
  fi
  validate_override_token "$_key" "$_value" || return 1
  printf '%s' "$_value"
}

resolve_super_projects_name() {
  resolve_override_token SUPER_PROJECTS_NAME "$DEFAULT_SUPER_PROJECTS_NAME"
}

resolve_super_projects_workdir() {
  resolve_override_token SUPER_PROJECTS_WORKDIR "$DEFAULT_SUPER_PROJECTS_WORKDIR"
}

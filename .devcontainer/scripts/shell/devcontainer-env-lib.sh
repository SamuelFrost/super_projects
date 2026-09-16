# Sourced by host initialize scripts (not executed). Callers must cd to the
# repository root first. Paths below are relative to that root.
#
# Shared .env parsers: strip Windows CRLF; SUPER_PROJECTS_NAME is validated
# separately because bind-mount values (e.g. 1Password sockets) may contain spaces.

NAMESPACE_OVERRIDE_FILE=.devcontainer/.env.namespace_override
DEFAULT_SUPER_PROJECTS_NAME=super_projects

env_file_var() {
  _file=$1
  _key=$2
  [ -f "$_file" ] || return 1
  _line=$(grep -m1 "^${_key}=" "$_file") || return 1
  _value=${_line#*=}
  _value=$(printf '%s' "$_value" | tr -d '\r')
  printf '%s' "$_value"
}

validate_super_projects_name() {
  _name=$1
  case "$_name" in
    '')
      echo "devcontainer env: SUPER_PROJECTS_NAME must not be empty" >&2
      return 1
      ;;
    *\"*|*"'"*)
      echo "devcontainer env: SUPER_PROJECTS_NAME must not be quoted" >&2
      return 1
      ;;
    *[[:space:]]*)
      echo "devcontainer env: SUPER_PROJECTS_NAME must not contain spaces" >&2
      return 1
      ;;
    export\ *)
      echo "devcontainer env: SUPER_PROJECTS_NAME must not use an export prefix" >&2
      return 1
      ;;
  esac
  if ! printf '%s' "$_name" | grep -Eq '^[a-z0-9][a-z0-9_-]*$'; then
    echo "devcontainer env: SUPER_PROJECTS_NAME must match [a-z0-9][a-z0-9_-]* (got: $_name)" >&2
    return 1
  fi
}

# Prints the resolved name. Reads .env.namespace_override when present; otherwise
# defaults to super_projects. Invalid values fail (do not start a misnamed project).
resolve_super_projects_name() {
  _name=$DEFAULT_SUPER_PROJECTS_NAME
  if [ -f "$NAMESPACE_OVERRIDE_FILE" ]; then
    if grep -q '^export SUPER_PROJECTS_NAME=' "$NAMESPACE_OVERRIDE_FILE"; then
      echo "devcontainer env: $NAMESPACE_OVERRIDE_FILE must use SUPER_PROJECTS_NAME=... not export SUPER_PROJECTS_NAME=" >&2
      return 1
    fi
    if grep -q '^SUPER_PROJECTS_NAME=' "$NAMESPACE_OVERRIDE_FILE"; then
      _name=$(env_file_var "$NAMESPACE_OVERRIDE_FILE" SUPER_PROJECTS_NAME) || _name=
    fi
  fi
  validate_super_projects_name "$_name" || return 1
  printf '%s' "$_name"
}

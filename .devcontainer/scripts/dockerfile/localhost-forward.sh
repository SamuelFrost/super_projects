#!/usr/bin/env bash
# Mirror published ports of docker compose stacks in the workspace onto 127.0.0.1 in this container.
#
# Chrome and chrome-devtools-mcp run here. A docker compose stack within the workspace publishes ports to the *host*, so http://localhost:<port> does not exist in this network namespace. This watcher finds those stacks (Compose working_dir or bind mounts under the workspace), attaches this container to their network, and forwards 127.0.0.1:<hostPort> to the container's private port (socat when present, otherwise a Python TCP proxy).
#
# Prefer the workspace copy so git pull applies without an image rebuild.
workspace_src=/workspaces/.devcontainer/scripts/dockerfile/localhost-forward.sh
if [[ -f "$workspace_src" && "${BASH_SOURCE[0]}" != "$workspace_src" ]]; then
  exec bash "$workspace_src" "$@"
fi

set -euo pipefail

PID_DIR="${LOCALHOST_FORWARD_PID_DIR:-/tmp/localhost-forward}"
WATCHER_PID_FILE="${PID_DIR}/watcher.pid"
WATCHER_LOG="${LOCALHOST_FORWARD_LOG:-/tmp/localhost-forward-watcher.log}"
STATUS_FILE="${PID_DIR}/status"
RESERVED_PORTS="${LOCALHOST_FORWARD_RESERVED_PORTS:-6080,5900,9223}"
SCRIPT_PATH="$workspace_src"
if [[ ! -f "$SCRIPT_PATH" ]]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
fi

mkdir -p "$PID_DIR"

log() {
  echo "localhost forwards: $*" | tee -a "$WATCHER_LOG" >&2
}

same_container_id() {
  local a="${1#sha256:}"
  local b="${2#sha256:}"
  [[ -z "$a" || -z "$b" ]] && return 1
  [[ "$a" == "$b" || "$a" == "$b"* || "$b" == "$a"* ]]
}

resolve_self_id() {
  local id
  id=$(sed -n 's|.*/containers/\([a-f0-9]\{12,64\}\).*|\1|p' /proc/self/mountinfo 2>/dev/null | head -n1 || true)
  if [[ -n "$id" ]] && docker inspect "$id" >/dev/null 2>&1; then
    echo "$id"
    return 0
  fi
  if docker inspect "${HOSTNAME}-devcontainer-1" >/dev/null 2>&1; then
    docker inspect -f '{{.Id}}' "${HOSTNAME}-devcontainer-1"
    return 0
  fi
  log "could not determine this container's ID" >&2
  return 1
}

path_is_under() {
  local path="$1"
  local prefix="$2"
  [[ -z "$path" || -z "$prefix" || "$path" == "<no value>" ]] && return 1
  prefix="${prefix%/}"
  path="${path%/}"
  [[ "$path" == "$prefix" || "$path" == "$prefix"/* ]]
}

is_blank() {
  [[ -z "${1:-}" || "$1" == "<no value>" ]]
}

load_workspace_prefixes() {
  WORKSPACE_PREFIXES=("/workspaces")
  local v="" line wd

  if [[ -n "${HOST_WORKSPACE_DIR:-}" ]]; then
    v="$HOST_WORKSPACE_DIR"
  elif [[ -f /workspaces/.devcontainer/.env ]]; then
    line=$(grep -E '^HOST_WORKSPACE_DIR=' /workspaces/.devcontainer/.env | tail -n1 || true)
    v="${line#HOST_WORKSPACE_DIR=}"
    v="${v%\"}"
    v="${v#\"}"
    v="${v%\'}"
    v="${v#\'}"
  fi
  [[ -n "$v" ]] && WORKSPACE_PREFIXES+=("$v")
  [[ -n "${LOCAL_WORKSPACE_FOLDER:-}" ]] && WORKSPACE_PREFIXES+=("$LOCAL_WORKSPACE_FOLDER")

  wd=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$SELF_ID" 2>/dev/null || true)
  if [[ "$wd" == */.devcontainer ]]; then
    WORKSPACE_PREFIXES+=("${wd%/.devcontainer}")
  fi
}

in_workspace() {
  local path="$1"
  local prefix
  is_blank "$path" && return 1
  for prefix in "${WORKSPACE_PREFIXES[@]}"; do
    path_is_under "$path" "$prefix" && return 0
  done
  return 1
}

is_workspace_container() {
  local cid="$1"
  local wd config_files bind_src

  wd=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$cid" 2>/dev/null) || return 1
  in_workspace "$wd" && return 0

  config_files=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$cid" 2>/dev/null) || return 1
  if ! is_blank "$config_files"; then
    local part parts
    IFS=', ' read -r -a parts <<<"$config_files"
    for part in "${parts[@]}"; do
      in_workspace "$part" && return 0
    done
  fi

  while IFS= read -r bind_src; do
    [[ -z "$bind_src" ]] && continue
    in_workspace "$bind_src" && return 0
  done < <(docker inspect -f '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}{{println}}{{end}}{{end}}' "$cid" 2>/dev/null || true)

  return 1
}

is_skippable_network() {
  local net="$1"
  local extra extra_net
  extra="${LOCALHOST_FORWARD_SKIP_NETWORKS:-}"
  case "$net" in
    bridge | host | none | ingress | docker_gwbridge) return 0 ;;
  esac
  if [[ -n "$extra" ]]; then
    IFS=',' read -r -a extra_nets <<<"$extra"
    for extra_net in "${extra_nets[@]}"; do
      extra_net="${extra_net#"${extra_net%%[![:space:]]*}"}"
      extra_net="${extra_net%"${extra_net##*[![:space:]]}"}"
      [[ "$net" == "$extra_net" ]] && return 0
    done
  fi
  return 1
}

docker_net_cmd() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 5 docker "$@"
  else
    docker "$@"
  fi
}

port_is_reserved() {
  local port="$1"
  local item
  IFS=',' read -r -a items <<<"$RESERVED_PORTS,$SELF_PUBLISHED_PORTS"
  for item in "${items[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [[ "$item" == "$port" ]] && return 0
  done
  return 1
}

load_self_published_ports() {
  SELF_PUBLISHED_PORTS=""
  local spec host_port
  while IFS= read -r spec; do
    [[ -z "$spec" ]] && continue
    host_port="${spec##* }"
    [[ "$host_port" =~ ^[0-9]+$ ]] || continue
    SELF_PUBLISHED_PORTS="${SELF_PUBLISHED_PORTS:+$SELF_PUBLISHED_PORTS,}${host_port}"
  done < <(docker inspect -f '{{range $p, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{range $bindings}}{{$p}} {{.HostPort}}{{println}}{{end}}{{end}}{{end}}' "$SELF_ID")
}

ensure_parent_on_child_network() {
  local cid="$1"
  local net parent_nets child_nets

  child_nets=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cid")
  parent_nets=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$SELF_ID")

  for net in $child_nets; do
    is_skippable_network "$net" && continue
    for existing in $parent_nets; do
      if [[ "$existing" == "$net" ]]; then
        echo "$net"
        return 0
      fi
    done
  done

  for net in $child_nets; do
    is_skippable_network "$net" && continue
    if docker_net_cmd network connect "$net" "$SELF_ID" >/dev/null 2>&1; then
      log "attached to network ${net}"
      echo "$net"
      return 0
    fi
    parent_nets=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$SELF_ID")
    for existing in $parent_nets; do
      if [[ "$existing" == "$net" ]]; then
        echo "$net"
        return 0
      fi
    done
  done

  return 1
}

child_ip_on_network() {
  local cid="$1"
  local net="$2"
  docker inspect -f "{{with index .NetworkSettings.Networks \"${net}\"}}{{.IPAddress}}{{end}}" "$cid"
}

stop_forward() {
  local listen_port="$1"
  local pid_file="$PID_DIR/${listen_port}.pid"
  local pid
  if [[ -f "$pid_file" ]]; then
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [[ -n "${pid:-}" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
  rm -f "$PID_DIR/${listen_port}.meta"
}

resolve_proxy_py() {
  local candidate
  for candidate in \
    "$(dirname "$SCRIPT_PATH")/localhost-forward-proxy.py" \
    /workspaces/.devcontainer/scripts/dockerfile/localhost-forward-proxy.py \
    /usr/local/lib/localhost-forward-proxy.py
  do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

start_forward() {
  local listen_port="$1"
  local target_ip="$2"
  local target_port="$3"
  local meta="$4"
  local pid_file="$PID_DIR/${listen_port}.pid"
  local log_file="/tmp/localhost-forward-${listen_port}.log"
  local proxy_py

  if command -v socat >/dev/null 2>&1; then
    nohup socat "TCP-LISTEN:${listen_port},bind=127.0.0.1,reuseaddr,fork" \
      "TCP:${target_ip}:${target_port}" \
      >"$log_file" 2>&1 &
  else
    proxy_py=$(resolve_proxy_py) || {
      log "neither socat nor localhost-forward-proxy.py is available"
      return 1
    }
    nohup python3 "$proxy_py" "$listen_port" "$target_ip" "$target_port" \
      >"$log_file" 2>&1 &
  fi
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "$meta" >"$PID_DIR/${listen_port}.meta"
  sleep 0.15
  if ! kill -0 "$pid" 2>/dev/null; then
    log "failed to listen on 127.0.0.1:${listen_port} (see ${log_file})"
    rm -f "$pid_file" "$PID_DIR/${listen_port}.meta"
    return 1
  fi
  return 0
}

collect_desired() {
  desired_lines=()
  local cid name listen_port private_spec private_port host_ip host_port net ip meta claimed

  while IFS= read -r cid; do
    [[ -z "$cid" ]] && continue
    same_container_id "$cid" "$SELF_ID" && continue
    docker inspect "$cid" >/dev/null 2>&1 || continue
    is_workspace_container "$cid" || continue

    name=$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null) || continue
    name="${name#/}"

    declared_ports=()
    while IFS= read -r spec; do
      [[ -z "$spec" ]] && continue
      private_spec="${spec%% *}"
      rest="${spec#* }"
      host_ip="${rest%% *}"
      host_port="${rest##* }"
      [[ "$private_spec" == */udp ]] && continue
      [[ "$host_port" =~ ^[0-9]+$ ]] || continue
      private_port="${private_spec%%/*}"
      [[ "$private_port" =~ ^[0-9]+$ ]] || continue
      port_is_reserved "$host_port" && continue

      claimed=""
      for existing in "${declared_ports[@]+"${declared_ports[@]}"}"; do
        [[ "${existing%% *}" == "$host_port" ]] && claimed=1 && break
      done
      [[ -n "$claimed" ]] && continue
      declared_ports+=("${host_port} ${private_port}")
    done < <(docker inspect -f '{{range $p, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{range $bindings}}{{$p}} {{.HostIp}} {{.HostPort}}{{println}}{{end}}{{end}}{{end}}' "$cid")

    [[ ${#declared_ports[@]} -eq 0 ]] && continue

    net=$(ensure_parent_on_child_network "$cid" || true)
    if [[ -z "${net:-}" ]]; then
      log "cannot reach ${name} (no attachable Docker network)"
      continue
    fi

    ip=$(child_ip_on_network "$cid" "$net")
    if [[ -z "$ip" ]]; then
      sleep 0.2
      ip=$(child_ip_on_network "$cid" "$net")
    fi
    if [[ -z "$ip" ]]; then
      log "no IPv4 address for ${name} on ${net}"
      continue
    fi

    for pair in "${declared_ports[@]}"; do
      listen_port="${pair%% *}"
      private_port="${pair##* }"
      meta="${ip} ${private_port} ${cid} ${name}"
      desired_lines+=("${listen_port} ${meta}")
    done
  done < <(docker ps -q)
}

sync_forwards() {
  mkdir -p "$PID_DIR"
  (
    flock 9
    _sync_forwards_body
  ) 9>"${PID_DIR}/sync.lock"
}

_sync_forwards_body() {

  load_self_published_ports
  collect_desired

  local -A desired_by_port=()
  local line listen_port meta other_cid other_name pid current_meta

  for line in "${desired_lines[@]+"${desired_lines[@]}"}"; do
    listen_port="${line%% *}"
    meta="${line#* }"
    if [[ -n "${desired_by_port[$listen_port]+x}" ]]; then
      other_name="${desired_by_port[$listen_port]##* }"
      log "skipping ${meta##* }:${listen_port} (already used by ${other_name})"
      continue
    fi
    desired_by_port["$listen_port"]="$meta"
  done

  for pid_file in "$PID_DIR"/*.pid; do
    [[ -f "$pid_file" ]] || continue
    [[ "$pid_file" == "$WATCHER_PID_FILE" ]] && continue
    listen_port="$(basename "$pid_file" .pid)"
    [[ "$listen_port" =~ ^[0-9]+$ ]] || continue
    meta="${desired_by_port[$listen_port]-}"
    current_meta=""
    [[ -f "$PID_DIR/${listen_port}.meta" ]] && current_meta=$(cat "$PID_DIR/${listen_port}.meta")
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [[ -z "$meta" ]]; then
      stop_forward "$listen_port"
      continue
    fi
    if [[ -z "${pid:-}" ]] || ! kill -0 "$pid" 2>/dev/null || [[ "$current_meta" != "$meta" ]]; then
      stop_forward "$listen_port"
    fi
  done

  local status="" target_ip target_port name
  if [[ ${#desired_by_port[@]} -eq 0 ]]; then
    echo "localhost forwards: none (publish a port on a workspace Compose service)" >"$STATUS_FILE"
    return 0
  fi
  for listen_port in "${!desired_by_port[@]}"; do
    meta="${desired_by_port[$listen_port]}"
    read -r target_ip target_port other_cid name <<<"$meta"
    if [[ -f "$PID_DIR/${listen_port}.pid" ]] && kill -0 "$(cat "$PID_DIR/${listen_port}.pid")" 2>/dev/null; then
      status="${status}  ${listen_port}→${name}:${target_port}"$'\n'
      continue
    fi
    if start_forward "$listen_port" "$target_ip" "$target_port" "$meta"; then
      status="${status}  ${listen_port}→${name}:${target_port}"$'\n'
    fi
  done

  if [[ -z "$status" ]]; then
    echo "localhost forwards: none (publish a port on a workspace Compose service)" >"$STATUS_FILE"
  else
    printf 'localhost forwards:\n%s' "$status" >"$STATUS_FILE"
  fi
}

stop_all_forwards() {
  local pid_file listen_port
  for pid_file in "$PID_DIR"/*.pid; do
    [[ -f "$pid_file" ]] || continue
    [[ "$pid_file" == "$WATCHER_PID_FILE" ]] && continue
    listen_port="$(basename "$pid_file" .pid)"
    [[ "$listen_port" =~ ^[0-9]+$ ]] || continue
    stop_forward "$listen_port"
  done
}

stop_watcher() {
  local pid child
  if [[ -f "$WATCHER_PID_FILE" ]]; then
    pid=$(cat "$WATCHER_PID_FILE" 2>/dev/null || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        kill "$child" 2>/dev/null || true
      done
      kill "$pid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$WATCHER_PID_FILE"
  fi
}

run_watch_loop() {
  set +e
  local heartbeat_pid
  : >"$WATCHER_LOG"
  SELF_ID=$(resolve_self_id) || exit 1
  load_workspace_prefixes
  load_self_published_ports
  sync_forwards
  (
    while true; do
      sleep 15
      sync_forwards
    done
  ) &
  heartbeat_pid=$!
  trap 'kill "$heartbeat_pid" 2>/dev/null; exit 0' TERM INT
  while read -r _; do
    sync_forwards
  done < <(docker events --filter type=container --format '{{.Action}}')
  kill "$heartbeat_pid" 2>/dev/null
}

start_daemon() {
  stop_watcher
  SELF_ID=$(resolve_self_id) || exit 1
  stop_all_forwards
  load_workspace_prefixes
  rm -f "$STATUS_FILE"
  nohup bash "$SCRIPT_PATH" watch </dev/null >>"$WATCHER_LOG" 2>&1 &
  echo $! >"$WATCHER_PID_FILE"
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if [[ -f "$STATUS_FILE" ]]; then
      cat "$STATUS_FILE"
      return 0
    fi
    sleep 0.3
  done
  log "watcher started (pid $(cat "$WATCHER_PID_FILE")); waiting for first scan"
  echo "localhost forwards: starting (log ${WATCHER_LOG})"
}

case "${1:-start}" in
  watch)
    run_watch_loop
    ;;
  once)
    SELF_ID=$(resolve_self_id) || exit 1
    load_workspace_prefixes
    sync_forwards
    cat "$STATUS_FILE"
    ;;
  stop)
    stop_watcher
    SELF_ID=$(resolve_self_id) || true
    stop_all_forwards
    echo "localhost forwards: stopped"
    ;;
  start | "")
    start_daemon
    ;;
  *)
    echo "Usage: start-localhost-forwards [start|stop|once]" >&2
    exit 2
    ;;
esac

#!/bin/sh
# Host-side devcontainer.json initializeCommand (before the container starts).
# VS Code, Cursor, and `devcontainer up` invoke this automatically.
set -eu

cd "$(dirname "$0")/../../.."

sh .devcontainer/docker_compose_configuration_customizations/ssh_agent_socket/write-compose-ssh-agent-socket
sh .devcontainer/docker_compose_configuration_customizations/host_filesystem_compatibility/write-compose-user-ids
sh .devcontainer/docker_compose_configuration_customizations/host_filesystem_compatibility/write-compose-project-directory
sh .devcontainer/docker_compose_configuration_customizations/ssh_known_hosts/write-compose-ssh-known-hosts
mkdir -p .devcontainer/persist/gemini .devcontainer/persist/gh .devcontainer/persist/git .devcontainer/persist/mise .devcontainer/persist/chrome .devcontainer/persist/cursor

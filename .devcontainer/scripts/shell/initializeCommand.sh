#!/bin/sh
# Host-side devcontainer.json initializeCommand (before the container starts).
# VS Code, Cursor, and `devcontainer up` invoke this automatically.
set -eu

cd "$(dirname "$0")/../../.."

sh .devcontainer/docker_compose_configuration_customizations/naming/create_override_file_if_missing
sh .devcontainer/docker_compose_configuration_customizations/miscellaneous_overrides/create_override_file_if_missing
sh .devcontainer/docker_compose_configuration_customizations/lllm/create_override_file_if_missing
sh .devcontainer/docker_compose_configuration_customizations/ssh_agent_socket/write-compose-ssh-agent-socket
sh .devcontainer/docker_compose_configuration_customizations/architecture/write-compose-architecture
sh .devcontainer/docker_compose_configuration_customizations/host_filesystem_compatibility/write-compose-user-ids
sh .devcontainer/docker_compose_configuration_customizations/host_filesystem_compatibility/write-compose-project-directory
sh .devcontainer/docker_compose_configuration_customizations/host_ide_settings/write-compose-host-ide-settings
sh .devcontainer/docker_compose_configuration_customizations/ssh_known_hosts/write-compose-ssh-known-hosts
mkdir -p \
	.devcontainer/persist/codex \
	.devcontainer/persist/chatgpt \
	.devcontainer/persist/claude-code \
	.devcontainer/persist/claude-desktop \
	.devcontainer/persist/cursor \
	.devcontainer/persist/cursor-config \
	.devcontainer/persist/cursor-desktop \
	.devcontainer/persist/cursor-server \
	.devcontainer/persist/vscode-profile \
	.devcontainer/persist/vscode-extensions \
	.devcontainer/persist/vscode-server \
	.devcontainer/persist/gemini \
	.devcontainer/persist/desktop-keyrings \
	.devcontainer/persist/gh \
	.devcontainer/persist/git \
	.devcontainer/persist/mise \
	.devcontainer/persist/chrome

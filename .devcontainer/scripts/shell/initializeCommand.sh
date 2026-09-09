#!/bin/sh
# Host-side devcontainer.json initializeCommand (before the container starts).
# VS Code, Cursor, and `devcontainer up` invoke this automatically.
set -eu

cd "$(dirname "$0")/../../.."

sh .devcontainer/scripts/shell/ensure-host-ssh-agent
sh .devcontainer/scripts/shell/write-devcontainer-env
mkdir -p .devcontainer/persist/gemini .devcontainer/persist/gh .devcontainer/persist/git .devcontainer/persist/mise .devcontainer/persist/chrome .devcontainer/persist/cursor

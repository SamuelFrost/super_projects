# Prefer mise-managed runtimes over editor-injected binaries (Cursor ships node on PATH).
# Shims resolve the correct version from the nearest .tool-versions / .mise.toml on each cd.
export PATH="${HOME}/.local/share/mise/shims:${PATH}"
eval "$(mise activate bash)"

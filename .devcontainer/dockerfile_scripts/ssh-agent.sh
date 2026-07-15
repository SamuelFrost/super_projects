export SSH_AUTH_SOCK="$HOME/.ssh/agent.sock"
_agent_sock="$SSH_AUTH_SOCK"
if [ -S "$_agent_sock" ]; then
  ssh-add -l >/dev/null 2>&1 || rm -f "$_agent_sock"
fi
if [ ! -S "$_agent_sock" ]; then
  eval "$(ssh-agent -a "$_agent_sock")"
fi
unset _agent_sock

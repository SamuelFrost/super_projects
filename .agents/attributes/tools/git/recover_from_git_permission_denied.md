# Tool interaction guideline — recover from Git permission denied

If Git fails with `Permission denied (publickey)`, run `ssh-add -l` in the container. If the agent is empty, **reopen the folder in the container** so host `initializeCommand` can unlock keys again, or use HTTPS: `gh auth login`. Private keys are not available inside the container.

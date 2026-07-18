# Domain context — GitHub CLI auth persistence

GitHub CLI auth persists in the `gh-data` named volume (`~/.config/gh`, also visible under `.devcontainer/persist/gh` inside the container). Run `gh auth login` **inside the container** once when needed (host `~/.config/gh` is separate). Tokens are stored in plain text on that volume (`hosts.yml`, mode `600`); wipe with `docker volume rm super_projects_gh-data`.

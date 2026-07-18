# Tool interaction guideline — use mise to execute commands

Use mise to execute commands when possible to avoid version-related issues, including hooks on commands that may be subsequently run, for example use `mise exec -- git commit` instead of `git commit`.

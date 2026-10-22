# Tool interaction guideline — Grep returns no matches in gitignored nested projects

Grep returns no matches under a nested project directory ignored by the workspace `.gitignore`, including when the file path is given directly. An empty result does not mean the file is missing. Read those paths directly.
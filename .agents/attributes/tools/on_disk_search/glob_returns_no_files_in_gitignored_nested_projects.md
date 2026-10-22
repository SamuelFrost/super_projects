# Tool interaction guideline — Glob returns no files in gitignored nested projects

Glob returns no files under a nested project directory ignored by the workspace `.gitignore`, including when that directory is the search root. An empty result does not mean the directory is missing. Read those paths directly.

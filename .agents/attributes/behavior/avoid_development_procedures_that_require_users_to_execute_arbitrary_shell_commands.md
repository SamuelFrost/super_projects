# Constraint — Avoid development procedures that require users to execute arbitrary shell commands

Avoid development procedures that require users to execute arbitrary shell, make file, or other executable files. Do not implement procedures in a way that requires a user to execute shell scripts directly.
It is okay to have it executed as part of an existing process, or as a hook for an existing process. However, any such procedure should be documented.
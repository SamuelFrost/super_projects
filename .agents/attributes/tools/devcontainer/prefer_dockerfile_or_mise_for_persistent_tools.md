# Tool installation guideline — prefer Dockerfile or mise for persistent tools

When installing new **tools/binaries**, prefer modifying the Dockerfile or using mise so they persist across rebuilds and can be shared with other developers. User **state** (auth, caches, profiles) belongs in the named volumes under `.devcontainer/persist/` (see `persist/README.md`), not in the image.

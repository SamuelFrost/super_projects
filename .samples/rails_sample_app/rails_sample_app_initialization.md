# Simple example project: create a new Rails project inside your fork

The following command creates a new Rails app as an untracked subdirectory of this repo (the parent-directory pattern).

```bash
docker run --rm --volume ${LOCAL_WORKSPACE_FOLDER:-.}:/app --workdir /app -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) ruby:latest bash -c 'gem install rails && rails new sample_app_1 --database=postgresql && chown -R $HOST_UID:$HOST_GID sample_app_1'
```
For best results, put a `docker-compose.yaml` in the sample app so Postgres and the app share a project network. `sample_app_1` already has this file; copy it when you create a new project.

Example `sample_app_1/docker-compose.yaml`:
```yaml
name: sample_app_1

services:
  sample_app_1:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - RAILS_ENV=development
      - SECRET_KEY_BASE=secret
      - DATABASE_URL=postgres://postgres:password@postgres:5432/sample_app_1_development
    ports:
      - "3000:80"
      # available on the host machine and the devcontainer at http://localhost:3000
      # available from the devcontainer at http://sample_app_1 when they share a Docker network
      # Note: To be able to access sample_app_1 (from within the devcontainer), Rails needs `config.hosts << "sample_app_1"` in development.rb
    volumes:
      # Compose uses the host Docker socket, so bind sources must be host paths.
      # Inside the parent, HOST_WORKSPACE_DIR (initializeCommand) and
      # LOCAL_WORKSPACE_FOLDER (devcontainer remoteEnv) are that host workspace.
      # On the host those vars are unset, so `..` is this project's parent.
      - ${HOST_WORKSPACE_DIR:-${LOCAL_WORKSPACE_FOLDER:-..}}/sample_app_1:/rails
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:18.3
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: sample_app_1_development
    volumes:
      - sample_app_1_postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  sample_app_1_postgres_data:
    external: false
    name: sample_app_1_postgres_data
```

## Browser access from the parent devcontainer

After `docker compose up`, open **http://localhost:3000** in the parent desktop Chrome (and chrome-devtools-mcp). Published `ports:` are mirrored onto `127.0.0.1` inside the parent container. That localhost URL does not need a Compose network entry or a Rails `config.hosts` change.

Details: [`.devcontainer/localhost-forwards.md`](../../.devcontainer/localhost-forwards.md).

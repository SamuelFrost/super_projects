# Simple example project: create a new Rails project inside your fork

<!-- note: the project is created as an untracked subdirectory of this repo (the parent-directory pattern). This fork's parent network is samuel_frost_personal_default. -->

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
      # available on the host machine at http://localhost:3000
      # available within the parent devcontainer at http://sample_app_1 when that container
      # shares samuel_frost_personal_default (add `config.hosts << "sample_app_1"` in development.rb)
    volumes:
      # LOCAL_WORKSPACE_FOLDER is the host path of the parent workspace (set by the
      # samuel_frost_personal devcontainer). When unset, `..` is this project's parent.
      - ${LOCAL_WORKSPACE_FOLDER:-..}/sample_app_1:/rails
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - default
      - samuel_frost_personal_default

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

networks:
  # Join the parent samuel_frost_personal network so Chrome in the devcontainer can
  # reach http://sample_app_1. App and Postgres talk on `default` without it.
  # The network must already exist (created by .devcontainer/compose.yaml).
  samuel_frost_personal_default:
    external: true

volumes:
  sample_app_1_postgres_data:
    external: false
    name: sample_app_1_postgres_data
```

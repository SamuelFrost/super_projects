# Runtime only: compose.yaml bind-mounts this directory and runs bin/localhost_forward_proxy from it,
# so code changes apply on the next sidecar restart without rebuilding this image.
FROM ruby:4.0.7-alpine

RUN apk add --no-cache docker-cli

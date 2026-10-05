# Code is copied into the image. Rebuild this image to pick up watcher or proxy changes.
FROM ruby:4.0.7-alpine

RUN apk add --no-cache docker-cli

COPY bin /opt/localhost_forward_proxy/bin
COPY lib /opt/localhost_forward_proxy/lib

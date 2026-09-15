FROM ruby:4.0-alpine

RUN apk add --no-cache docker-cli

WORKDIR /opt/localhost_forward_proxy
COPY . /opt/localhost_forward_proxy

# Compose bind-mounts the workspace and runs the copy under /${SUPER_PROJECTS_WORKDIR} so git pull
# applies without rebuilding. This image copy is the fallback when that mount is absent.
ENV RUBYLIB=/opt/localhost_forward_proxy/lib
CMD ["ruby", "/opt/localhost_forward_proxy/bin/localhost_forward_proxy"]

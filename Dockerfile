FROM ghcr.io/astral-sh/uv:latest AS uv

FROM docker.io/python:3.14-alpine3.22

LABEL org.opencontainers.image.authors="Said Sef <said@saidsef.co.uk> (saidsef.co.uk/)"
LABEL org.opencontainers.image.source="https://github.com/saidsef/k8s-spot-termination-notice"
LABEL org.opencontainers.image.description="Kubernetes Spot Instance Notification"
LABEL org.opencontainers.image.licenses="MIT"

ARG BUILD_ID=""

ENV BUILD_ID=${BUILD_ID:-'beta-0'}
ENV VERSION="3.1"
ENV SLACK_API_TOKEN=${SLACK_API_TOKEN}
ENV SLACK_CHANNEL=${SLACK_CHANNEL}
ENV UV_PROJECT_ENVIRONMENT="/app/.venv"
ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock /app/
COPY spot.py /app/

RUN apk add --update --no-cache ca-certificates && \
    uv sync --frozen --no-dev && \
    chown -R 10001:10001 .

USER 10001

CMD ["spot.py"]
ENTRYPOINT ["python"]

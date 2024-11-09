FROM docker.io/python:3.12-alpine3.18

LABEL maintainer="Said Sef said@saidsef.co.uk (saidsef.co.uk/)"

ARG BUILD_ID

ENV BUILD_ID ${BUILD_ID:-'beta-0'}
ENV VERSION "3.1"
ENV SLACK_API_TOKEN ${SLACK_API_TOKEN}
ENV SLACK_CHANNEL ${SKACK_CHANNEL}

WORKDIR /app

COPY spot.py /app
COPY requirements.txt /app

RUN apk add --update --no-cache ca-certificates && \
    pip --no-cache-dir install -r requirements.txt && \
    chown -R 10001:10001 .

USER 10001

CMD ["spot.py"]
ENTRYPOINT ["python"]

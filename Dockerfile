FROM python:3-alpine

LABEL maintainer="Said Sef said@saidsef.co.uk (saidsef.co.uk/)"

ENV VERSION "1.0"
ENV SLACK_API_TOKEN ${SLACK_API_TOKEN}
ENV SLACK_CHANNEL ${SKACK_CHANNEL}

WORKDIR /app

COPY . /app

RUN apk add --update --no-cache ca-certificates && \
    pip --no-cache-dir install -r requirements.txt && \
    rm -rfv /var/cache/apk/* && \
    rm -rfv /root/.cache/* && \
    chown -R nobody:nobody .

USER nobody

CMD ["spot.py"]
ENTRYPOINT ["python"]

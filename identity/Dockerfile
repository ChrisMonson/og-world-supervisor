FROM python:3.13-alpine

RUN adduser -D -u 10002 identity && mkdir -p /identity && chown identity:identity /identity

COPY service.py /app/service.py

ENV IDENTITY_DB=/identity/identity.db \
    IDENTITY_PORT=8090

EXPOSE 8090
VOLUME ["/identity"]

USER identity
ENTRYPOINT ["python3", "/app/service.py"]

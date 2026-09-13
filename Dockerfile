# Image of the Study 1 web demo.
#
# The build context is the repo ROOT, not web/: the container needs protocol/
# (the experiment content) and common/ (the loader and the agent) besides the
# server.
#
# No pip install: the server is standard library only.

FROM python:3.11-slim

WORKDIR /app

COPY protocol/ ./protocol/
COPY common/ ./common/
COPY web/ ./web/

ENV PORT=8080 \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "-m", "web.server.app"]

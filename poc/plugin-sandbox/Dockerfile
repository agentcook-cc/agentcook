FROM python:3.11-slim

RUN groupadd -r sandbox && useradd -r -g sandbox -s /bin/false sandbox

WORKDIR /workspace

USER sandbox

ENTRYPOINT ["python"]

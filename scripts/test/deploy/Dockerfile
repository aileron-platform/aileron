FROM --platform=linux/amd64 python:3.9-slim@sha256:dad5b29e3506c35e0fd222736f4d4ef25d21b219acdd73f7bb41d59996ca8e0d AS deployment-python39-lock

COPY scripts/deploy/rke2/requirements.txt /opt/aileron-deploy/requirements.txt
RUN python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement /opt/aileron-deploy/requirements.txt \
    && python -m pip check \
    && python -c "import sys, jsonschema, yaml; assert sys.version_info[:2] == (3, 9)"

WORKDIR /repo
COPY scripts/deploy/rke2 /repo/scripts/deploy/rke2
RUN set -eu; \
    for script_path in /repo/scripts/deploy/rke2/*.py; do \
      python "${script_path}" --help >/dev/null; \
    done; \
    python -c "from pathlib import Path; Path('/opt/aileron-deploy/python39-lock.verified').write_text('python3.9-locked-runtime=verified\\n', encoding='utf-8')"

FROM python:3.12-slim@sha256:bf73779de6dbd030f3d189eeeb246286965832761ace318c1518300f76c0840d

ARG SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=${SOURCE_REVISION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends jq \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/test/deploy/requirements.txt /opt/aileron-test/requirements.txt
RUN pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement /opt/aileron-test/requirements.txt

COPY --from=deployment-python39-lock /opt/aileron-deploy/python39-lock.verified /opt/aileron-deploy/python39-lock.verified

WORKDIR /repo

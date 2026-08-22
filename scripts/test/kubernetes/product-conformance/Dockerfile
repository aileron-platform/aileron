FROM python:3.12-slim@sha256:bf73779de6dbd030f3d189eeeb246286965832761ace318c1518300f76c0840d

ARG SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=${SOURCE_REVISION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/product-conformance

COPY scripts/test/kubernetes/product-conformance/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY scripts/test/kubernetes/product-conformance/product_conformance ./product_conformance
COPY contracts/platform-configuration/runtime-platform-environment.json \
    ./contracts/runtime-platform-environment.json

ENTRYPOINT ["python", "-m", "product_conformance.driver"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/product-conformance

COPY scripts/test/kubernetes/product-conformance/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/test/kubernetes/product-conformance/product_conformance ./product_conformance

ENTRYPOINT ["python", "-m", "product_conformance.driver"]

FROM redis:7.4.9-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99

COPY --chmod=0555 entrypoint.sh /usr/local/bin/aileron-redis-entrypoint

RUN chown 65532:65532 /data \
    && chmod 0770 /data

USER 65532:65532

ENTRYPOINT ["/usr/local/bin/aileron-redis-entrypoint"]
CMD ["--appendonly", "yes", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]

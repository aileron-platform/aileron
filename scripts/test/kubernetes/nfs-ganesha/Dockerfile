FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        netcat-openbsd \
        dbus-daemon \
        nfs-ganesha \
        nfs-ganesha-vfs \
        rpcbind \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/test/kubernetes/nfs-ganesha/ganesha.conf /etc/ganesha/ganesha.conf
COPY scripts/test/kubernetes/nfs-ganesha/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 0755 /usr/local/bin/entrypoint.sh

EXPOSE 2049/tcp

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

FROM quay.io/keycloak/keycloak:26.7.0@sha256:0f198be292568439d700cdbfb893e69a6009bb43a94a06a945b1d3d506c76b13 AS builder

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=false

RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.7.0@sha256:0f198be292568439d700cdbfb893e69a6009bb43a94a06a945b1d3d506c76b13

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=false

COPY --from=builder /opt/keycloak/ /opt/keycloak/
COPY --chown=1000:1000 --chmod=0555 entrypoint.sh /opt/aileron/bin/entrypoint.sh

USER 1000:1000

ENTRYPOINT ["/opt/aileron/bin/entrypoint.sh"]

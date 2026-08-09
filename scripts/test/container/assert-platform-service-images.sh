#!/bin/sh

set -eu

redis_image="${REDIS_IMAGE:?REDIS_IMAGE is required}"
postgres_image="${POSTGRES_IMAGE:?POSTGRES_IMAGE is required}"
storage_gid="${STORAGE_GID:-2000}"
runtime_uid="1000860000"
run_suffix="$(date +%s)-$$"
resource_prefix="aileron-platform-contract-${run_suffix}"
network="${resource_prefix}"
redis_volume="${resource_prefix}-redis"
postgres_volume="${resource_prefix}-postgres"
redis_container="${resource_prefix}-redis"
postgres_container="${resource_prefix}-postgres"

fail() {
  printf 'Platform service image assertion failed: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  docker rm -f \
    "${postgres_container}" \
    "${redis_container}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
  docker volume rm "${postgres_volume}" "${redis_volume}" >/dev/null 2>&1 || true
}

trap cleanup EXIT HUP INT TERM

assert_numeric_non_root_user() {
  image="$1"
  configured_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"
  case "${configured_user}" in
    [1-9][0-9]*:[1-9][0-9]*) ;;
    *) fail "${image} must declare a numeric non-root uid:gid USER, found '${configured_user}'" ;;
  esac
}

prepare_group_writable_volume() {
  image="$1"
  volume="$2"
  docker volume create "${volume}" >/dev/null
  docker run --rm \
    --user 0:0 \
    --volume "${volume}:/volume" \
    --entrypoint /bin/sh \
    "${image}" \
    -ec "
      chgrp '${storage_gid}' /volume
      chmod 2770 /volume
      touch /volume/.aileron-volume-ready
      chgrp '${storage_gid}' /volume/.aileron-volume-ready
      chmod 0660 /volume/.aileron-volume-ready
    "
}

wait_for_redis() {
  attempts=60
  while [ "${attempts}" -gt 0 ]; do
    if docker exec "${redis_container}" redis-cli ping 2>/dev/null | grep -qx PONG; then
      return
    fi
    if [ "$(docker inspect --format '{{.State.Running}}' "${redis_container}" 2>/dev/null || true)" != true ]; then
      docker logs "${redis_container}" >&2 || true
      fail "Redis exited before readiness"
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  docker logs "${redis_container}" >&2 || true
  fail "Redis readiness deadline exceeded"
}

start_redis() {
  docker run --detach \
    --name "${redis_container}" \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --tmpfs "/tmp:rw,noexec,nosuid,size=16m,uid=${runtime_uid},gid=${runtime_uid},mode=0770" \
    --user "${runtime_uid}:${runtime_uid}" \
    --group-add "${storage_gid}" \
    --volume "${redis_volume}:/data" \
    "${redis_image}" \
    --appendonly yes \
    --maxmemory 32mb \
    --maxmemory-policy allkeys-lru >/dev/null
  wait_for_redis
}

assert_redis_contract() {
  entrypoint="$(docker image inspect --format '{{join .Config.Entrypoint " "}}' "${redis_image}")"
  [ "${entrypoint}" = "/usr/local/bin/aileron-redis-entrypoint" ] || \
    fail "Redis must use the direct Aileron entrypoint"

  prepare_group_writable_volume "${redis_image}" "${redis_volume}"
  start_redis
  docker exec "${redis_container}" redis-cli set contract-key persisted | grep -qx OK || \
    fail "Redis write probe failed"
  docker stop --time 20 "${redis_container}" >/dev/null
  docker rm "${redis_container}" >/dev/null

  start_redis
  docker exec "${redis_container}" redis-cli get contract-key | grep -qx persisted || \
    fail "Redis append-only restart did not preserve data"
  if docker logs "${redis_container}" 2>&1 | grep -q 'chown:'; then
    fail "Redis attempted a runtime chown"
  fi
  docker stop --time 20 "${redis_container}" >/dev/null
  docker rm "${redis_container}" >/dev/null
}

wait_for_postgres() {
  attempts=120
  while [ "${attempts}" -gt 0 ]; do
    if docker exec "${postgres_container}" pg_isready \
      --host 127.0.0.1 --port 5432 \
      --username contract --dbname contract >/dev/null 2>&1; then
      return
    fi
    if [ "$(docker inspect --format '{{.State.Running}}' "${postgres_container}" 2>/dev/null || true)" != true ]; then
      docker logs "${postgres_container}" >&2 || true
      fail "Postgres exited before readiness"
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  docker logs "${postgres_container}" >&2 || true
  fail "Postgres readiness deadline exceeded"
}

start_postgres() {
  docker run --detach \
    --name "${postgres_container}" \
    --network "${network}" \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --tmpfs "/tmp:rw,noexec,nosuid,size=64m,uid=${runtime_uid},gid=${runtime_uid},mode=0770" \
    --tmpfs "/var/run/postgresql:rw,noexec,nosuid,size=16m,uid=${runtime_uid},gid=${runtime_uid},mode=0770" \
    --user "${runtime_uid}:${runtime_uid}" \
    --group-add "${storage_gid}" \
    --env POSTGRES_DB=contract \
    --env POSTGRES_USER=contract \
    --env POSTGRES_PASSWORD=contract-password \
    --env POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 \
    --env PGDATA=/var/lib/postgresql/data/pgdata \
    --volume "${postgres_volume}:/var/lib/postgresql/data" \
    "${postgres_image}" >/dev/null
  wait_for_postgres
}

assert_postgres_contract() {
  prepare_group_writable_volume "${postgres_image}" "${postgres_volume}"
  docker network create "${network}" >/dev/null
  start_postgres

  docker exec \
    --env PGPASSWORD=contract-password \
    "${postgres_container}" \
    psql --host 127.0.0.1 --username contract --dbname contract \
      --set ON_ERROR_STOP=1 \
      --command 'CREATE TABLE contract_restart (value text NOT NULL); INSERT INTO contract_restart VALUES (current_user);' \
      >/dev/null
  if docker exec \
    --env PGPASSWORD=wrong-password \
    "${postgres_container}" \
    psql --host 127.0.0.1 --username contract --dbname contract \
      --command 'SELECT 1' >/dev/null 2>&1; then
    fail "Postgres accepted an invalid TCP password"
  fi

  docker stop --time 30 "${postgres_container}" >/dev/null
  docker rm "${postgres_container}" >/dev/null
  start_postgres
  docker exec \
    --env PGPASSWORD=contract-password \
    "${postgres_container}" \
    psql --host 127.0.0.1 --username contract --dbname contract \
      --tuples-only --no-align \
      --command 'SELECT value FROM contract_restart' | grep -qx contract || \
    fail "Postgres high-UID restart did not preserve data"
}

for image in "${redis_image}" "${postgres_image}"; do
  assert_numeric_non_root_user "${image}"
done

assert_redis_contract
assert_postgres_contract

printf 'Platform Redis and Postgres image contracts passed.\n'

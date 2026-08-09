#!/bin/sh

set -eu

repo_root=${1:-/repo}
compose_file="${repo_root}/workspace-operator/docker-compose.turn.test.yml"

cleanup() {
  docker compose -f "${compose_file}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose -f "${compose_file}" run --rm turn-probe-test

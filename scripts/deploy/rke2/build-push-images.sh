#!/bin/sh

set -eu
umask 077

repository_root="$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)"
cd "${repository_root}"

: "${HARBOR_REGISTRY:?HARBOR_REGISTRY is required}"
: "${HARBOR_PROJECT:?HARBOR_PROJECT is required}"

case "${OMIT_IMAGE_COMPONENTS:-}" in
  ""|platform-redis) ;;
  *)
    echo "OMIT_IMAGE_COMPONENTS contains a forbidden component" >&2
    exit 1
    ;;
esac

for command_name in docker git jq python3; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "Required command is unavailable: ${command_name}" >&2
    exit 1
  }
done

bake_file="${repository_root}/docker-bake.hcl"

resolve_node_slim_image() {
  resolved_node_image="$(
    awk '
      /^[[:space:]]*variable[[:space:]]+"NODE_SLIM_IMAGE"[[:space:]]*\{/ {
        in_node_variable = 1
        next
      }
      in_node_variable && /^[[:space:]]*\}/ {
        in_node_variable = 0
        next
      }
      in_node_variable &&
        /^[[:space:]]*default[[:space:]]*=[[:space:]]*"[^"]+"[[:space:]]*$/ {
        value = $0
        sub(/^[^"]*"/, "", value)
        sub(/"[[:space:]]*$/, "", value)
        print value
      }
    ' "${bake_file}"
  )"
  resolved_node_image_count="$(
    printf '%s\n' "${resolved_node_image}" |
      awk 'NF { count += 1 } END { print count + 0 }'
  )"
  if [ "${resolved_node_image_count}" -ne 1 ] ||
    ! printf '%s\n' "${resolved_node_image}" |
      grep -Eq '^[^[:space:]@]+@sha256:[0-9a-f]{64}$'; then
    echo "docker-bake.hcl must define exactly one digest-pinned NODE_SLIM_IMAGE default" >&2
    exit 1
  fi
  printf '%s' "${resolved_node_image}"
}

printf '%s' "${HARBOR_REGISTRY}" |
  grep -Eq '^[a-z0-9][a-z0-9.-]*(:[0-9]{1,5})?$' || {
  echo "HARBOR_REGISTRY must be a hostname with an optional port" >&2
  exit 1
}

append_no_proxy() {
  current_value="$1"
  registry_endpoint="$2"
  case ",${current_value}," in
    *",${registry_endpoint},"*)
      printf '%s' "${current_value}"
      ;;
    ",,")
      printf '%s' "${registry_endpoint}"
      ;;
    *)
      printf '%s,%s' "${current_value}" "${registry_endpoint}"
      ;;
  esac
}

registry_host="${HARBOR_REGISTRY%%:*}"
NO_PROXY="$(append_no_proxy "${NO_PROXY:-}" "${registry_host}")"
no_proxy="$(append_no_proxy "${no_proxy:-}" "${registry_host}")"
if [ "${HARBOR_REGISTRY}" != "${registry_host}" ]; then
  NO_PROXY="$(append_no_proxy "${NO_PROXY}" "${HARBOR_REGISTRY}")"
  no_proxy="$(append_no_proxy "${no_proxy}" "${HARBOR_REGISTRY}")"
fi
export NO_PROXY no_proxy

printf '%s' "${HARBOR_PROJECT}" |
  grep -Eq '^[a-z0-9]+([._-][a-z0-9]+)*$' || {
  echo "Harbor project names must use valid lowercase syntax" >&2
  exit 1
}

if [ "$(uname -m)" != "x86_64" ]; then
  echo "RKE2 image publication must run on the amd64 build host" >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "RKE2 image publication requires a clean Git checkout" >&2
  exit 1
fi

commit="$(git rev-parse --verify HEAD)"
if [ -n "${EXPECTED_COMMIT:-}" ] &&
  ! printf '%s' "${EXPECTED_COMMIT}" | grep -Eq '^[0-9a-f]{40}$'; then
  echo "EXPECTED_COMMIT must be a full lowercase Git SHA" >&2
  exit 1
fi
[ -z "${EXPECTED_COMMIT:-}" ] || [ "${commit}" = "${EXPECTED_COMMIT}" ] || {
  echo "Git HEAD does not match EXPECTED_COMMIT" >&2
  exit 1
}
short_commit="$(git rev-parse --short=12 HEAD)"
[ -z "${IMAGE_TAG:-}" ] || {
  echo "IMAGE_TAG is not supported; image tags are derived from Git HEAD" >&2
  exit 1
}
tag="git-${commit}"
output_file="${OUTPUT_FILE:-/tmp/aileron-image-digests-${short_commit}.tsv}"
[ ! -L "${output_file}" ] || {
  echo "OUTPUT_FILE must not be a symbolic link" >&2
  exit 1
}
if [ -e "${output_file}" ] && [ ! -f "${output_file}" ]; then
  echo "OUTPUT_FILE must be a regular file path" >&2
  exit 1
fi
output_directory="$(dirname -- "${output_file}")"
[ -d "${output_directory}" ] || {
  echo "OUTPUT_FILE parent directory does not exist" >&2
  exit 1
}

node_slim_image="$(resolve_node_slim_image)"

temporary_output="$(mktemp -- "${output_file}.tmp.XXXXXX")"
remote_inspect_error=""
verified_image_digest=""
verified_runtime_digest=""

cleanup_temporary_files() {
  rm -f "${temporary_output}"
  if [ -n "${remote_inspect_error}" ]; then
    rm -f "${remote_inspect_error}"
  fi
}

trap cleanup_temporary_files EXIT
trap 'exit 130' HUP INT TERM

image_ref() {
  target_project="$1"
  component="$2"
  printf '%s/%s/%s:%s' \
    "${HARBOR_REGISTRY}" "${target_project}" "${component}" "${tag}"
}

record_digest() {
  component="$1"
  image="$2"
  printf '%s' "${verified_image_digest}" |
    grep -Eq '^sha256:[0-9a-f]{64}$' ||
    {
      echo "The verified image document did not contain a lowercase sha256 digest for ${image}" >&2
      exit 1
    }
  printf '%s' "${verified_runtime_digest}" |
    grep -Eq '^sha256:[0-9a-f]{64}$' ||
    {
      echo "The verified linux/amd64 manifest did not contain a lowercase sha256 digest for ${image}" >&2
      exit 1
    }
  [ "${verified_image_digest}" != "${verified_runtime_digest}" ] || {
    echo "The OCI index and linux/amd64 manifest digests must be distinct for ${image}" >&2
    exit 1
  }
  printf '%s\t%s\tlinux/amd64\t%s\t%s@%s\t%s@%s\n' \
    "${component}" "${commit}" "${image}" \
    "${image%:*}" "${verified_image_digest}" \
    "${image%:*}" "${verified_runtime_digest}" >> "${temporary_output}"
}

reuse_remote_image() {
  image="$1"
  verified_image_digest=""
  verified_runtime_digest=""
  remote_inspect_error="$(mktemp -- "${output_file}.inspect.XXXXXX")"
  if remote_document="$(
    docker buildx imagetools inspect "${image}" \
      --format '{{json .}}' \
      2>"${remote_inspect_error}"
  )"; then
    rm -f "${remote_inspect_error}"
    remote_inspect_error=""
    if ! verified_digest_pair="$(
      printf '%s\n' "${remote_document}" |
        jq -er \
        --arg commit "${commit}" \
        --arg image "${image}" \
        '
          def lowercase_sha256:
            type == "string"
            and test("^sha256:[0-9a-f]{64}$");

          select(type == "object")
          | select(
              .name == $image
              and (.image | type) == "object"
              and .image.os == "linux"
              and .image.architecture == "amd64"
              and (.image.config | type) == "object"
              and (.image.config.Labels | type) == "object"
              and .image.config.Labels["org.opencontainers.image.revision"]
                == $commit
            )
          | select(
              (.manifest | type) == "object"
              and .manifest.mediaType
                == "application/vnd.oci.image.index.v1+json"
              and (.manifest.digest | lowercase_sha256)
              and (.manifest.manifests | type) == "array"
              and (.manifest.manifests | length) > 0
            )
          | . as $document
          | (
            [
              $document.manifest.manifests[]
              | select(
                  type == "object"
                  and (.platform | type == "object")
                  and .platform.os == "linux"
                  and .platform.architecture == "amd64"
                )
            ]
          ) as $runtime_manifests
          | select(($runtime_manifests | length) == 1)
          | $runtime_manifests[0].digest as $runtime_digest
          | select($runtime_digest | lowercase_sha256)
          | select(
              all(
                $document.manifest.manifests[];
                type == "object"
                and .mediaType
                  == "application/vnd.oci.image.manifest.v1+json"
                and (.digest | lowercase_sha256)
                and (.platform | type) == "object"
                and (
                  (
                    .platform.os == "linux"
                    and .platform.architecture == "amd64"
                  )
                  or (
                    .platform.os == "unknown"
                    and .platform.architecture == "unknown"
                    and (.annotations | type) == "object"
                    and .annotations["vnd.docker.reference.type"]
                      == "attestation-manifest"
                    and .annotations["vnd.docker.reference.digest"]
                      == $runtime_digest
                  )
                )
              )
            )
          | [$document.manifest.digest, $runtime_digest]
        ' 2>/dev/null
    )"; then
      verified_image_digest=""
      verified_runtime_digest=""
      echo "Existing immutable image does not match the expected linux/amd64 provenance and revision: ${image}" >&2
      exit 1
    fi
    if ! verified_image_digest="$(
      printf '%s\n' "${verified_digest_pair}" | jq -er '.[0]'
    )" || ! verified_runtime_digest="$(
      printf '%s\n' "${verified_digest_pair}" | jq -er '.[1]'
    )"; then
      verified_image_digest=""
      verified_runtime_digest=""
      echo "Existing immutable image did not expose an exact index/runtime digest pair: ${image}" >&2
      exit 1
    fi
    printf 'Reusing immutable image %s\n' "${image}"
    return 0
  fi

  remote_error_document="$(
    cat "${remote_inspect_error}"
    printf '%s' '__AILERON_IMAGE_INSPECT_END__'
  )"
  expected_absent_document="$(
    printf 'ERROR: %s: not found\n%s' \
      "${image}" '__AILERON_IMAGE_INSPECT_END__'
  )"
  if [ "${remote_error_document}" = "${expected_absent_document}" ]; then
    rm -f "${remote_inspect_error}"
    remote_inspect_error=""
    return 1
  fi

  echo "Remote image inspection failed; refusing to treat the error as an absent tag: ${image}" >&2
  exit 1
}

verify_published_image() {
  image="$1"
  if reuse_remote_image "${image}"; then
    return
  fi
  echo "Published image could not be read back from the registry: ${image}" >&2
  exit 1
}

publish_bake() {
  component="$1"
  bake_target="$2"
  target_project="${3:-${HARBOR_PROJECT}}"
  image="$(image_ref "${target_project}" "${component}")"

  if ! reuse_remote_image "${image}"; then
    IMAGE_NAMESPACE="${HARBOR_REGISTRY}/${HARBOR_PROJECT}" \
      LOCAL_TAG="${tag}" \
      RELEASE_TAG="${tag}" \
      NODE_SLIM_IMAGE="${node_slim_image}" \
      docker buildx bake \
        --file "${bake_file}" \
        --push \
        --set "${bake_target}.platform=linux/amd64" \
        --set "${bake_target}.tags=${image}" \
        --set "${bake_target}.labels.org.opencontainers.image.revision=${commit}" \
        "${bake_target}"
    verify_published_image "${image}"
  fi

  record_digest "${component}" "${image}"
}

publish_dockerfile() {
  component="$1"
  dockerfile="$2"
  context="$3"
  image="$(image_ref "${HARBOR_PROJECT}" "${component}")"

  if ! reuse_remote_image "${image}"; then
    docker buildx build \
      --platform linux/amd64 \
      --label "org.opencontainers.image.revision=${commit}" \
      --file "${dockerfile}" \
      --tag "${image}" \
      --push \
      "${context}"
    verify_published_image "${image}"
  fi

  record_digest "${component}" "${image}"
}

publish_bake workspace-ui workspace-ui-production
publish_bake workspace-manager workspace-manager-kubernetes
publish_bake workspace-runtime-base-lite runtime-base-lite
publish_bake workspace-runtime workspace-runtime-kubernetes
publish_bake workspace-chrome workspace-browser-kubernetes
publish_bake workspace-canvas workspace-canvas-kubernetes
publish_bake workspace-operator workspace-operator-kubernetes
publish_bake platform-keycloak platform-keycloak
publish_dockerfile platform-postgres platform/postgres/Dockerfile platform/postgres
if [ "${OMIT_IMAGE_COMPONENTS:-}" != platform-redis ]; then
  publish_dockerfile platform-redis platform/redis/Dockerfile platform/redis
fi
publish_dockerfile platform-coturn platform/coturn/Dockerfile platform/coturn

set -- \
  "${temporary_output}" \
  --expected-commit "${commit}" \
  --expected-registry "${HARBOR_REGISTRY}" \
  --expected-project "${HARBOR_PROJECT}"
if [ "${OMIT_IMAGE_COMPONENTS:-}" = platform-redis ]; then
  set -- "$@" --omit-component platform-redis
fi
python3 "${repository_root}/scripts/deploy/rke2/release_inventory.py" "$@" >/dev/null

mv -- "${temporary_output}" "${output_file}"
trap - EXIT HUP INT TERM

printf 'commit=%s\n' "${commit}"
printf 'tag=%s\n' "${tag}"
printf 'digest_file=%s\n' "${output_file}"

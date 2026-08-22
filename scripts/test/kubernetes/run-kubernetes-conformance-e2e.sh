#!/bin/sh

set -eu

umask 0077

repo_root="${REPO_ROOT:-/repo}"
artifact_root="${ARTIFACT_DIR:-/artifacts}"
run_id="${E2E_RUN_ID:-$(date -u +%Y%m%d%H%M%S)-$$}"
namespace="${E2E_NAMESPACE:-aileron-kubernetes-e2e-${run_id}}"
mode="${E2E_MODE:-local}"
storage_mode="${E2E_STORAGE_MODE:-static-nfs}"
keep_namespace="${KEEP_E2E_NAMESPACE:-false}"
require_product_lifecycle="${REQUIRE_PRODUCT_LIFECYCLE:-false}"
root_squash_mode="${ROOT_SQUASH_MODE:-pod}"
image_pull_secret_source_namespace="${IMAGE_PULL_SECRET_SOURCE_NAMESPACE:-}"
image_pull_secret_source_name="${IMAGE_PULL_SECRET_SOURCE_NAME:-}"
image_pull_secret_name="${IMAGE_PULL_SECRET_NAME:-${image_pull_secret_source_name}}"
workspace_contract_output_dir="${WORKSPACE_CR_CONTRACT_OUTPUT_DIR:-}"

workspace_id="11111111-1111-4111-8111-111111111111"
workspace_name="workspace-${workspace_id}"
workspace_digest="$(printf '%s' "${workspace_id}" | sha256sum | cut -d ' ' -f 1)"
kb_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
instance_1="10000000-0000-4000-8000-000000000001"
instance_2="10000000-0000-4000-8000-000000000002"
instance_3="10000000-0000-4000-8000-000000000003"
instance_4="10000000-0000-4000-8000-000000000004"
instance_5="10000000-0000-4000-8000-000000000005"
instance_6="10000000-0000-4000-8000-000000000006"
runtime_secret_name="$(printf 'workspace-generation-%.16s' "${workspace_digest}")"

operator_image="${OPERATOR_IMAGE:?OPERATOR_IMAGE is required}"
manager_image="${MANAGER_IMAGE:?MANAGER_IMAGE is required}"
workload_probe_image="${WORKLOAD_PROBE_IMAGE:?WORKLOAD_PROBE_IMAGE is required}"
workspace_browser_image="${workload_probe_image}"
workload_probe_image_file="${WORKLOAD_PROBE_IMAGE_FILE:-}"
product_workload_images_file="${PRODUCT_WORKLOAD_IMAGES_FILE:-}"
image_pull_policy="${IMAGE_PULL_POLICY:-Never}"
nfs_server="${NFS_SERVER:-nfs-server}"
storage_class="${RWX_STORAGE_CLASS:-nfs-rwx-${run_id}}"
rwo_storage_class="${RWO_STORAGE_CLASS:-${storage_class}}"
runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-${rwo_storage_class}}"
runtime_home_access_mode="${RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"
shared_storage_size="${E2E_SHARED_STORAGE_SIZE:-1Gi}"
rwo_storage_size="${E2E_RWO_STORAGE_SIZE:-1Gi}"
runtime_home_storage_size="${E2E_RUNTIME_HOME_STORAGE_SIZE:-2Gi}"

storage_quantity_to_bytes() {
  quantity="$1"
  case "${quantity}" in
    *Ki) printf '%s' "$(( ${quantity%Ki} * 1024 ))" ;;
    *Mi) printf '%s' "$(( ${quantity%Mi} * 1048576 ))" ;;
    *Gi) printf '%s' "$(( ${quantity%Gi} * 1073741824 ))" ;;
    *Ti) printf '%s' "$(( ${quantity%Ti} * 1099511627776 ))" ;;
    *[0-9]) printf '%s' "${quantity}" ;;
    *) printf 'unsupported storage quantity: %s\n' "${quantity}" >&2; exit 1 ;;
  esac
}

workspace_data_capacity_bytes="$(storage_quantity_to_bytes "${shared_storage_size}")"
runtime_home_capacity_bytes="$(storage_quantity_to_bytes "${runtime_home_storage_size}")"
requested_storage_gid="${PLATFORM_STORAGE_GID:-2000}"
expected_scc="${EXPECTED_SCC:-}"
node_a="${E2E_NODE_A:-}"
node_b="${E2E_NODE_B:-}"

artifact_dir="${artifact_root}/${run_id}"
render_dir="/tmp/aileron-kubernetes-e2e-${run_id}"
result="failed"
product_lifecycle_verified="false"
namespace_created="false"
operator_verified="false"
runtime_scoped_secrets_isolated_verified="false"
manager_write_verified="false"
rwo_state_persistence_verified="false"
storage_setgid_verified="false"
storage_negative_verified="false"
root_squash_verified="false"
nfs_lock_verified="false"
uid_transition_verified="false"
runtime_ro_verified="false"
knowledge_base_cross_node_verified="false"
workspace_rwx_verified="false"
runtime_home_persistence_verified="false"
generation_fencing_verified="false"
generation_watch_uid_binding_verified="false"
generation_watch_process_verified="false"
deployment_watch_status_refresh_verified="false"
same_generation_status_refresh_verified="false"
pod_watch_pipeline_verified="false"
access_only_mount_contract_verified="false"
deployment_stability_verified="false"
content_update_verified="false"
openshift_admission_verified="false"
storage_gid=""
explicit_fs_group=""
uid_a="${STORAGE_UID_A:-}"
uid_b="${STORAGE_UID_B:-}"
generation_watch_pid=""
generation_watch_file=""
generation_watch_error_file=""
generation_watch_raw_file=""

log() {
  printf '[kubernetes-conformance-e2e] %s\n' "$*"
}

fail() {
  log "FAILED: $*" >&2
  exit 1
}

kube() {
  if command -v kubectl >/dev/null 2>&1; then
    kubectl "$@"
    return
  fi
  if command -v k3s >/dev/null 2>&1; then
    k3s kubectl "$@"
    return
  fi
  fail "kubectl or k3s is required"
}

wait_for_file() {
  path="$1"
  attempts="${2:-180}"
  while [ "${attempts}" -gt 0 ]; do
    if [ -s "${path}" ]; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  return 1
}

wait_until() {
  description="$1"
  shift
  attempts="${E2E_WAIT_ATTEMPTS:-240}"
  while [ "${attempts}" -gt 0 ]; do
    if "$@"; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  fail "timed out waiting for ${description}"
}

prepare_kubeconfig() {
  if [ -n "${K3S_KUBECONFIG_SOURCE:-}" ]; then
    wait_for_file "${K3S_KUBECONFIG_SOURCE}" 240 || fail "k3s kubeconfig was not created"
    server_name="${K3S_SERVER_NAME:-k3s-server}"
    sed "s/127\\.0\\.0\\.1/${server_name}/g" \
      "${K3S_KUBECONFIG_SOURCE}" > "${render_dir}/kubeconfig.yaml"
    export KUBECONFIG="${render_dir}/kubeconfig.yaml"
  fi
  [ -n "${KUBECONFIG:-}" ] || fail "KUBECONFIG is required"
  [ -r "${KUBECONFIG}" ] || fail "KUBECONFIG is not readable: ${KUBECONFIG}"
}

schedulable_ready_node_names() {
  kube get nodes --no-headers 2>/dev/null | awk '$2 == "Ready" {print $1}' | \
    while IFS= read -r candidate; do
      [ -n "${candidate}" ] || continue
      unschedulable="$(kube get node "${candidate}" -o jsonpath='{.spec.unschedulable}' 2>/dev/null || true)"
      [ "${unschedulable}" != "true" ] || continue
      if kube get node "${candidate}" \
        -o jsonpath='{range .spec.taints[*]}{.effect}{"\n"}{end}' 2>/dev/null | \
        grep -Eq '^(NoSchedule|NoExecute)$'; then
        continue
      fi
      printf '%s\n' "${candidate}"
    done
}

cluster_ready() {
  kube get --raw=/readyz >/dev/null 2>&1 || return 1
  ready_nodes="$(schedulable_ready_node_names | awk 'NF {count++} END {print count + 0}')"
  [ "${ready_nodes}" -ge 2 ]
}

select_nodes() {
  if [ -z "${node_a}" ] || [ -z "${node_b}" ]; then
    ready_node_names="$(schedulable_ready_node_names)"
    ready_node_count="$(printf '%s\n' "${ready_node_names}" | awk 'NF {count++} END {print count + 0}')"
    [ "${ready_node_count}" -ge 2 ] || fail "at least two Ready nodes are required"
    first_ready_node="$(printf '%s\n' "${ready_node_names}" | sed -n '1p')"
    second_ready_node="$(printf '%s\n' "${ready_node_names}" | sed -n '2p')"
    node_a="${node_a:-${first_ready_node}}"
    node_b="${node_b:-${second_ready_node}}"
  fi
  [ "${node_a}" != "${node_b}" ] || fail "E2E_NODE_A and E2E_NODE_B must be different"
  eligible_nodes="$(schedulable_ready_node_names)"
  for selected_node in "${node_a}" "${node_b}"; do
    printf '%s\n' "${eligible_nodes}" | grep -Fxq "${selected_node}" || \
      fail "selected node is not Ready and schedulable: ${selected_node}"
  done
  log "using nodes ${node_a} and ${node_b}"
}

namespace_annotation() {
  annotation="$1"
  kube get namespace "${namespace}" \
    -o "go-template={{ index .metadata.annotations \"${annotation}\" }}" 2>/dev/null || true
}

range_start() {
  value="$1"
  printf '%s' "${value%%/*}"
}

resolve_storage_identity() {
  if [ "${requested_storage_gid}" = "AUTO" ]; then
    range=""
    attempts=60
    while [ "${attempts}" -gt 0 ] && [ -z "${range}" ]; do
      range="$(namespace_annotation 'openshift.io/sa.scc.supplemental-groups')"
      attempts=$((attempts - 1))
      [ -n "${range}" ] || sleep 1
    done
    [ -n "${range}" ] || fail "OpenShift supplemental group range was not assigned"
    storage_gid="$(range_start "${range}")"
    explicit_fs_group=""
  else
    storage_gid="${requested_storage_gid}"
    explicit_fs_group="${storage_gid}"
  fi
  case "${storage_gid}" in
    ''|*[!0-9]*) fail "PLATFORM_STORAGE_GID must be a positive integer or AUTO" ;;
  esac
  [ "${storage_gid}" -gt 0 ] || fail "PLATFORM_STORAGE_GID must be positive"

  if [ -z "${uid_a}" ] || [ -z "${uid_b}" ]; then
    if [ -n "${expected_scc}" ]; then
      uid_range=""
      attempts=60
      while [ "${attempts}" -gt 0 ] && [ -z "${uid_range}" ]; do
        uid_range="$(namespace_annotation 'openshift.io/sa.scc.uid-range')"
        attempts=$((attempts - 1))
        [ -n "${uid_range}" ] || sleep 1
      done
      [ -n "${uid_range}" ] || fail "OpenShift UID range was not assigned"
      uid_start="$(range_start "${uid_range}")"
      uid_a=$((uid_start + 1))
      uid_b=$((uid_start + 2))
    else
      uid_a="1000860000"
      uid_b="1000860001"
    fi
  fi
  [ "${uid_a}" != "${uid_b}" ] || fail "storage transition UIDs must differ"
}

render_fs_group_block() {
  indent="$1"
  if [ -n "${explicit_fs_group}" ]; then
    printf '%sfsGroup: %s\n%sfsGroupChangePolicy: OnRootMismatch\n' \
      "${indent}" "${explicit_fs_group}" "${indent}"
  fi
}

create_namespace() {
  if kube get namespace "${namespace}" >/dev/null 2>&1; then
    fail "namespace already exists: ${namespace}"
  fi
  kube create namespace "${namespace}" >/dev/null
  namespace_created="true"
  kube label namespace "${namespace}" \
    aileron.io/test-run-id="${run_id}" \
    --overwrite >/dev/null
}

copy_image_pull_secret() {
  [ -n "${image_pull_secret_name}" ] || return 0
  IMAGE_PULL_SECRET_SOURCE_NAMESPACE="${image_pull_secret_source_namespace}" \
  IMAGE_PULL_SECRET_SOURCE_NAME="${image_pull_secret_source_name}" \
  IMAGE_PULL_SECRET_NAME="${image_pull_secret_name}" \
  IMAGE_PULL_SECRET_TARGET_NAMESPACE="${namespace}" \
  IMAGE_PULL_SECRET_ARTIFACT_DIR="${artifact_dir}" \
    "${repo_root}/scripts/test/kubernetes/image-pull-secret.sh"
}

render_image_pull_secrets() {
  indent="$1"
  if [ -n "${image_pull_secret_name}" ]; then
    printf '%simagePullSecrets:\n%s  - name: %s\n' \
      "${indent}" "${indent}" "${image_pull_secret_name}"
  fi
}

is_immutable_image_reference() {
  printf '%s\n' "$1" | grep -Eq \
    '^[a-z0-9]([a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$'
}

resolve_workload_probe_image() {
  if [ -n "${workload_probe_image_file}" ]; then
    wait_for_file "${workload_probe_image_file}" 60 || \
      fail "workload probe image reference was not created: ${workload_probe_image_file}"
    workload_probe_image="$(sed -n '1p' "${workload_probe_image_file}")"
  fi
  if is_immutable_image_reference "${workload_probe_image}"; then
    return 0
  fi
  fail "WORKLOAD_PROBE_IMAGE must be an immutable image reference: ${workload_probe_image}"
}

resolve_product_workload_image() {
  image="$1"
  if is_immutable_image_reference "${image}"; then
    printf '%s\n' "${image}"
    return 0
  fi
  [ -n "${product_workload_images_file}" ] || \
    fail "product workload image must be immutable: ${image}"
  wait_for_file "${product_workload_images_file}" 60 || \
    fail "product workload image references were not created: ${product_workload_images_file}"
  resolved_image="$(
    awk -v source_image="${image}" \
      '$1 == source_image { print $2; exit }' \
      "${product_workload_images_file}"
  )"
  [ -n "${resolved_image}" ] || \
    fail "product workload image digest was not exported: ${image}"
  is_immutable_image_reference "${resolved_image}" || \
    fail "exported product workload image is not immutable: ${resolved_image}"
  printf '%s\n' "${resolved_image}"
}

setup_storage() {
  if [ "${storage_mode}" = "static-nfs" ]; then
    [ "${rwo_storage_class}" = "${storage_class}" ] || \
      fail "static-nfs requires RWO_STORAGE_CLASS to match RWX_STORAGE_CLASS"
    [ "${runtime_home_storage_class}" = "${storage_class}" ] || \
      fail "static-nfs requires RUNTIME_HOME_STORAGE_CLASS to match RWX_STORAGE_CLASS"
    storage_manifest="${render_dir}/rwx-nfs-storage.yaml"
    sed \
      -e "s/__RUN_ID__/${run_id}/g" \
      -e "s/__NAMESPACE__/${namespace}/g" \
      -e "s/__WORKSPACE_ID__/${workspace_id}/g" \
      -e "s/__NFS_SERVER__/${nfs_server}/g" \
      -e "s/__STORAGE_CLASS__/${storage_class}/g" \
      -e "s/__RUNTIME_HOME_ACCESS_MODE__/${runtime_home_access_mode}/g" \
      "${repo_root}/scripts/test/kubernetes/manifests/rwx-nfs-storage.yaml" \
      > "${storage_manifest}"
    kube apply -f "${storage_manifest}" >/dev/null
  elif [ "${storage_mode}" = "dynamic" ]; then
    kube get storageclass "${storage_class}" >/dev/null 2>&1 || \
      fail "RWX storage class does not exist: ${storage_class}"
    kube get storageclass "${rwo_storage_class}" >/dev/null 2>&1 || \
      fail "RWO storage class does not exist: ${rwo_storage_class}"
    kube get storageclass "${runtime_home_storage_class}" >/dev/null 2>&1 || \
      fail "Runtime HOME storage class does not exist: ${runtime_home_storage_class}"
    cat > "${render_dir}/dynamic-pvcs.yaml" <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: knowledge-bases-pvc
  namespace: ${namespace}
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: ${shared_storage_size}
  storageClassName: ${storage_class}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: manager-state-pvc
  namespace: ${namespace}
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: ${rwo_storage_size}
  storageClassName: ${rwo_storage_class}
EOF
    kube apply -f "${render_dir}/dynamic-pvcs.yaml" >/dev/null
  else
    fail "unsupported E2E_STORAGE_MODE: ${storage_mode}"
  fi
  kube wait --for=jsonpath='{.status.phase}'=Bound \
    "pvc/knowledge-bases-pvc" \
    -n "${namespace}" --timeout=240s >/dev/null
}

install_operator() {
  WORKSPACE_CRD_MANIFEST="${repo_root}/helm/aileron/crds/platform.aileron.io_workspaces.yaml" \
  WORKSPACE_CRD_ARTIFACT_DIR="${artifact_dir}" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" ensure

  operator_fs_group="$(render_fs_group_block '        ')"
  operator_service_account_pull_secrets="$(render_image_pull_secrets '')"
  operator_storage_env=""
  operator_image_pull_secret_env=""
  if [ -n "${explicit_fs_group}" ]; then
    operator_storage_env="            - name: PLATFORM_STORAGE_GID
              value: \"${explicit_fs_group}\""
  fi
  if [ -n "${image_pull_secret_name}" ]; then
    operator_image_pull_secret_env="            - name: WORKSPACE_IMAGE_PULL_SECRET_NAMES
              value: \"${image_pull_secret_name}\""
  fi
  cat > "${render_dir}/operator.yaml" <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workspace-operator
  namespace: ${namespace}
${operator_service_account_pull_secrets}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: workspace-operator
  namespace: ${namespace}
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "persistentvolumeclaims", "serviceaccounts", "events", "configmaps", "secrets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["cilium.io"]
    resources: ["ciliumnetworkpolicies"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["platform.aileron.io"]
    resources: ["workspaces", "workspaces/status", "workspaces/finalizers"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: workspace-operator
  namespace: ${namespace}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: workspace-operator
subjects:
  - kind: ServiceAccount
    name: workspace-operator
    namespace: ${namespace}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: workspace-operator-storageclasses-${run_id}
  labels:
    aileron.io/test-run-id: ${run_id}
rules:
  - apiGroups: ["storage.k8s.io"]
    resources: ["storageclasses"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: workspace-operator-storageclasses-${run_id}
  labels:
    aileron.io/test-run-id: ${run_id}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: workspace-operator-storageclasses-${run_id}
subjects:
  - kind: ServiceAccount
    name: workspace-operator
    namespace: ${namespace}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workspace-operator
  namespace: ${namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: workspace-operator
  template:
    metadata:
      labels:
        app: workspace-operator
    spec:
      serviceAccountName: workspace-operator
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
${operator_fs_group}
      containers:
        - name: workspace-operator
          image: ${operator_image}
          imagePullPolicy: ${image_pull_policy}
          args:
            - --metrics-bind-address=0
          env:
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
            - name: KNOWLEDGE_BASES_PVC_NAME
              value: knowledge-bases-pvc
            - name: BROWSER_CREDENTIAL_KEYRING_FILE
              value: /etc/aileron/browser-credentials/keyring.json
            - name: AILERON_PLATFORM_PUBLIC_ORIGIN
              value: https://aileron.example.test
            - name: AILERON_MANAGER_INTERNAL_URL
              value: http://workspace-manager.${namespace}.svc.cluster.local:3001
            - name: CILIUM_ENABLED
              value: "false"
            - name: WORKSPACE_STORAGE_CLASS_NAME
              value: ${storage_class}
            - name: WORKSPACE_STORAGE_SIZE
              value: ${shared_storage_size}
            - name: RUNTIME_HOME_STORAGE_CLASS_NAME
              value: ${runtime_home_storage_class}
            - name: RUNTIME_HOME_STORAGE_SIZE
              value: ${runtime_home_storage_size}
            - name: RUNTIME_HOME_STORAGE_ACCESS_MODE
              value: ${runtime_home_access_mode}
${operator_image_pull_secret_env}
${operator_storage_env}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: [ALL]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: browser-credential-keyring
              mountPath: /etc/aileron/browser-credentials
              readOnly: true
      volumes:
        - name: tmp
          emptyDir: {}
        - name: browser-credential-keyring
          secret:
            secretName: browser-credential-keyring
            defaultMode: 0440
            items:
              - key: keyring.json
                path: keyring.json
EOF
  kube apply -f "${render_dir}/operator.yaml" >/dev/null
  if ! kube rollout status deployment/workspace-operator \
    -n "${namespace}" --timeout=180s >/dev/null; then
    kube describe deployment/workspace-operator -n "${namespace}" >&2 || true
    kube logs deployment/workspace-operator -n "${namespace}" >&2 || true
    fail "workspace-operator did not become Ready"
  fi
  operator_verified="true"
}

create_runtime_secrets() {
  kube create secret generic runtime-assertion-public-jwks \
    -n "${namespace}" \
    --from-literal='jwks.json={"keys":[]}' >/dev/null
  kube create secret generic browser-credential-keyring \
    -n "${namespace}" \
    --from-literal='keyring.json={"algorithm":"hkdf-sha256-v1","activeKeyId":"e2e-browser-credential-v1","keys":{"e2e-browser-credential-v1":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}}' \
    >/dev/null
  kube create secret generic "${runtime_secret_name}" \
    -n "${namespace}" \
    --from-literal='runtime-database-connection=postgresql://runtime_e2e:runtime_e2e@postgres.invalid:5432/runtime_e2e' \
    --from-literal='runtime-control-token=e2e-generation-scoped-opaque-control-token' \
    --from-literal='custom-setup.sh=:' \
    >/dev/null
}

create_manager_writer() {
  writer_fs_group="$(render_fs_group_block '    ')"
  cat > "${render_dir}/manager-writer.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: manager-writer
  namespace: ${namespace}
  labels:
    app.kubernetes.io/component: manager-writer
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_b}
  securityContext:
    runAsNonRoot: true
    runAsUser: ${uid_a}
    runAsGroup: ${uid_a}
    seccompProfile:
      type: RuntimeDefault
${writer_fs_group}
  containers:
    - name: manager-writer
      image: ${manager_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args:
        - |
          test "\$(id -u)" -ne 0
          for root in /knowledge-bases /state; do
            root_mode="\$(stat -c '%a' "\${root}")"
            test "\$((0\${root_mode} & 02000))" -ne 0
            root_gid="\$(stat -c '%g' "\${root}")"
            id -G | tr ' ' '\n' | grep -qx "\${root_gid}"
          done
          umask 0007
          mkdir -p "/knowledge-bases/${kb_id}"
          printf '%s\n' 'fixture-v1' > "/knowledge-bases/${kb_id}/fixture.txt"
          test "\${HOME}" = /state/home
          mkdir -p /state/home /state/codex /state/local-history /state/uploads /state/marketplace
          touch \
            /state/manager-write-probe \
            /state/home/home-write-probe \
            /state/codex/codex-write-probe \
            /state/local-history/local-history-write-probe \
            /state/uploads/uploads-write-probe \
            /state/marketplace/marketplace-write-probe
          exec sleep 3600
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: manager-state
          mountPath: /state
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: manager-state
      persistentVolumeClaim:
        claimName: manager-state-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/manager-writer.yaml" >/dev/null
  if ! kube wait --for=jsonpath='{.status.phase}'=Bound \
    "pvc/manager-state-pvc" \
    -n "${namespace}" --timeout=240s >/dev/null; then
    kube describe pvc/manager-state-pvc -n "${namespace}" >&2 || true
    kube describe pod/manager-writer -n "${namespace}" >&2 || true
    fail "Manager state PVC did not bind after creating its consumer"
  fi
  if ! kube wait --for=condition=Ready pod/manager-writer \
    -n "${namespace}" --timeout=240s >/dev/null; then
    kube describe pod/manager-writer -n "${namespace}" >&2 || true
    kube logs pod/manager-writer -n "${namespace}" >&2 || true
    fail "Manager canonical writer did not become Ready"
  fi
  effective_uid="$(kube exec -n "${namespace}" manager-writer -- id -u)"
  [ "${effective_uid}" = "${uid_a}" ] || fail "Manager writer effective UID mismatch"
  kube exec -n "${namespace}" manager-writer -- \
    grep -qx fixture-v1 "/knowledge-bases/${kb_id}/fixture.txt"
  printf 'path mode uid gid\n' > "${artifact_dir}/manager-storage-paths.txt"
  kube exec -n "${namespace}" manager-writer -- stat -c '%n %a %u %g' \
    /knowledge-bases \
    "/knowledge-bases/${kb_id}" \
    "/knowledge-bases/${kb_id}/fixture.txt" \
    /state \
    /state/home \
    /state/codex \
    /state/local-history \
    /state/uploads \
    /state/marketplace \
    >> "${artifact_dir}/manager-storage-paths.txt"
  # Expand the positional parameter inside the Manager writer Pod.
  # shellcheck disable=SC2016
  kube exec -n "${namespace}" manager-writer -- /bin/sh -ec \
    'printf "%s\n" "$1" > /state/.aileron-rwo-persistence' \
    -- "rwo-state-${run_id}"
  first_manager_pod_uid="$(kube get pod manager-writer -n "${namespace}" \
    -o jsonpath='{.metadata.uid}')"
  kube delete pod manager-writer -n "${namespace}" --wait=true >/dev/null
  kube apply -f "${render_dir}/manager-writer.yaml" >/dev/null
  kube wait --for=condition=Ready pod/manager-writer \
    -n "${namespace}" --timeout=240s >/dev/null
  second_manager_pod_uid="$(kube get pod manager-writer -n "${namespace}" \
    -o jsonpath='{.metadata.uid}')"
  [ "${second_manager_pod_uid}" != "${first_manager_pod_uid}" ] || \
    fail "Manager state probe Pod UID did not change after recreation"
  kube exec -n "${namespace}" manager-writer -- \
    grep -qx "rwo-state-${run_id}" /state/.aileron-rwo-persistence
  printf 'first_pod_uid\tsecond_pod_uid\taccess_mode\tstorage_class\n' \
    > "${artifact_dir}/rwo-state-recreate.tsv"
  printf '%s\t%s\tReadWriteOnce\t%s\n' \
    "${first_manager_pod_uid}" \
    "${second_manager_pod_uid}" \
    "${rwo_storage_class}" \
    >> "${artifact_dir}/rwo-state-recreate.tsv"
  manager_write_verified="true"
  rwo_state_persistence_verified="true"
  storage_setgid_verified="true"
}

assert_wrong_storage_group_rejected() {
  if [ -n "${expected_scc}" ]; then
    log "skipping wrong-group probe because the OpenShift SCC injects storage groups"
    return
  fi

  cat > "${render_dir}/wrong-storage-group-probe.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: wrong-storage-group-probe
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_b}
  securityContext:
    runAsNonRoot: true
    runAsUser: ${uid_a}
    runAsGroup: ${uid_a}
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: wrong-storage-group-probe
      image: ${workload_probe_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args: ["touch /knowledge-bases/.wrong-storage-group-probe"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/wrong-storage-group-probe.yaml" >/dev/null
  attempts="${E2E_WAIT_ATTEMPTS:-240}"
  phase=""
  while [ "${attempts}" -gt 0 ]; do
    phase="$(kube get pod wrong-storage-group-probe -n "${namespace}" \
      -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    case "${phase}" in
      Failed|Succeeded) break ;;
    esac
    attempts=$((attempts - 1))
    sleep 1
  done
  case "${phase}" in
    Failed|Succeeded) ;;
    *) fail "wrong storage group probe did not reach a terminal phase" ;;
  esac
  kube get pod/wrong-storage-group-probe -n "${namespace}" -o yaml \
    > "${artifact_dir}/wrong-storage-group-probe.yaml"
  kube logs pod/wrong-storage-group-probe -n "${namespace}" \
    > "${artifact_dir}/wrong-storage-group-probe.log" 2>&1 || true
  if [ "${phase}" = "Succeeded" ]; then
    if [ "${mode}" != "diagnostic" ]; then
      fail "wrong storage group unexpectedly wrote to the canonical root"
    fi
    printf '%s\n' \
      'wrong storage group write succeeded; this run is not certification eligible' \
      > "${artifact_dir}/wrong-storage-group-diagnostic.txt"
    kube exec -n "${namespace}" manager-writer -- \
      rm -f /knowledge-bases/.wrong-storage-group-probe
    kube delete pod/wrong-storage-group-probe -n "${namespace}" \
      --wait=true >/dev/null
    log "diagnostic mode recorded an unenforced storage group boundary"
    return
  fi
  exit_code="$(kube get pod wrong-storage-group-probe -n "${namespace}" \
    -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}')"
  [ "${exit_code}" -ne 0 ] || fail "wrong storage group unexpectedly wrote to the canonical root"
  kube exec -n "${namespace}" manager-writer -- \
    test ! -e /knowledge-bases/.wrong-storage-group-probe
  kube delete pod/wrong-storage-group-probe -n "${namespace}" --wait=true >/dev/null
  storage_negative_verified="true"
}

assert_root_squash() {
  if [ "${root_squash_mode}" = "evidence" ]; then
    evidence="${ROOT_SQUASH_EVIDENCE_FILE:?ROOT_SQUASH_EVIDENCE_FILE is required}"
    [ -s "${evidence}" ] || fail "root-squash evidence is empty: ${evidence}"
    grep -Eq '"rootSquash"[[:space:]]*:[[:space:]]*true([[:space:]]*[,}]|[[:space:]]*$)' "${evidence}" || \
      fail "root-squash evidence does not certify rootSquash=true"
    cp "${evidence}" "${artifact_dir}/root-squash-evidence.json"
    root_squash_verified="true"
    return
  fi
  [ "${root_squash_mode}" = "pod" ] || fail "ROOT_SQUASH_MODE must be pod or evidence"

  squash_fs_group="$(render_fs_group_block '    ')"
  cat > "${render_dir}/root-squash-probe.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: root-squash-probe
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_b}
  securityContext:
    runAsUser: 0
    runAsGroup: 0
    seccompProfile:
      type: RuntimeDefault
${squash_fs_group}
  containers:
    - name: root-squash-probe
      image: ${workload_probe_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args: ["touch /knowledge-bases/root-squash-probe"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/root-squash-probe.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Succeeded pod/root-squash-probe \
    -n "${namespace}" --timeout=120s >/dev/null
  squashed_uid="$(kube exec -n "${namespace}" manager-writer -- \
    stat -c '%u' /knowledge-bases/root-squash-probe)"
  [ "${squashed_uid}" != "0" ] || fail "NFS root client retained UID 0"
  cat > "${artifact_dir}/root-squash-evidence.json" <<EOF
{
  "rootSquash": true,
  "observedFileUid": ${squashed_uid},
  "probe": "in-cluster-uid-0-client"
}
EOF
  kube get pod/root-squash-probe -n "${namespace}" -o yaml \
    > "${artifact_dir}/root-squash-probe.yaml"
  kube delete pod/root-squash-probe -n "${namespace}" --wait=true >/dev/null
  root_squash_verified="true"
}

assert_locking() {
  lock_fs_group="$(render_fs_group_block '    ')"
  cat > "${render_dir}/lock-holder.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: nfs-lock-holder
  namespace: ${namespace}
  labels:
    aileron.io/e2e-lock-role: holder
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_a}
  securityContext:
    runAsNonRoot: true
    runAsUser: ${uid_a}
    runAsGroup: ${uid_a}
    seccompProfile:
      type: RuntimeDefault
${lock_fs_group}
  containers:
    - name: holder
      image: ${manager_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["python3", "-c"]
      args:
        - "import fcntl,os,pathlib,time; os.umask(0o007); f=open('/knowledge-bases/${kb_id}/.lock','w'); fcntl.flock(f,fcntl.LOCK_EX); pathlib.Path('/knowledge-bases/${kb_id}/.lock-ready').write_text('ready'); time.sleep(120)"
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: tmp
      emptyDir: {}
---
apiVersion: v1
kind: Pod
metadata:
  name: nfs-lock-contender
  namespace: ${namespace}
  labels:
    aileron.io/e2e-lock-role: contender
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_b}
  securityContext:
    runAsNonRoot: true
    runAsUser: ${uid_b}
    runAsGroup: ${uid_b}
    seccompProfile:
      type: RuntimeDefault
${lock_fs_group}
  containers:
    - name: contender
      image: ${manager_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["python3", "-c"]
      args:
        - "import fcntl,sys; f=open('/knowledge-bases/${kb_id}/.lock','r+');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(0)\nsys.exit(1)"
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/lock-holder.yaml" \
    -l aileron.io/e2e-lock-role=holder >/dev/null
  wait_until "NFS lock holder" kube exec -n "${namespace}" manager-writer -- \
    test -f "/knowledge-bases/${kb_id}/.lock-ready"
  kube apply -f "${render_dir}/lock-holder.yaml" \
    -l aileron.io/e2e-lock-role=contender >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Succeeded pod/nfs-lock-contender \
    -n "${namespace}" --timeout=120s >/dev/null
  kube get pod/nfs-lock-holder pod/nfs-lock-contender -n "${namespace}" -o yaml \
    > "${artifact_dir}/nfs-lock-probes.yaml"
  kube delete pod/nfs-lock-holder pod/nfs-lock-contender \
    -n "${namespace}" --ignore-not-found --wait=true >/dev/null
  kube exec -n "${namespace}" manager-writer -- \
    rm -f "/knowledge-bases/${kb_id}/.lock" "/knowledge-bases/${kb_id}/.lock-ready"
  nfs_lock_verified="true"
}

render_workspace_manifest() {
  destination="$1"
  cat > "${destination}" <<EOF
apiVersion: platform.aileron.io/v1alpha1
kind: Workspace
metadata:
  name: ${workspace_name}
  namespace: ${namespace}
spec:
  workspaceId: ${workspace_id}
  ownerId: e2e-owner
  provisioner: kubernetes
  targetNamespace: ${namespace}
  bootstrap:
    revision: 1
  runtime:
    image: ${workload_probe_image}
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: "2"
        memory: 3Gi
    runtimeSecretName: ${runtime_secret_name}
    desiredState: Running
    instanceId: ${instance_1}
    revision: 1
    mountRevision: 0
    accessRevision: 0
    assertion:
      issuer: workspace-manager-e2e
      publicKeySetSecretName: runtime-assertion-public-jwks
  browser:
    enabled: true
    desiredState: Running
    instanceId: ${instance_1}
    revision: 1
    image: ${workspace_browser_image}
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: "2"
        memory: 2Gi
    credentialSecretName: workspace-browser-credential-${workspace_id}-r1
    credentialRevision: 1
    credentialKeyId: e2e-browser-credential-v1
    credentialAlgorithm: hkdf-sha256-v1
  canvas:
    enabled: true
    desiredState: Running
    instanceId: ${instance_1}
    revision: 1
    image: ${workload_probe_image}
    resources:
      requests:
        cpu: 100m
        memory: 1Gi
      limits:
        cpu: "1"
        memory: 2Gi
  workspacePath: /workspace
  worktreeSubdir: .worktrees
  knowledgeBases: []
  storage:
    workspaceData:
      capacityBytes: ${workspace_data_capacity_bytes}
      revision: 1
    runtimeHome:
      capacityBytes: ${runtime_home_capacity_bytes}
      revision: 1
  firewall:
    revision: 1
    workspace:
      egressMode: blocked
      allowedDomains: []
    browser:
      egressMode: blocked
      allowedDomains: []
EOF
}

create_workspace() {
  render_workspace_manifest "${render_dir}/workspace.yaml"
  kube apply -f "${render_dir}/workspace.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Running \
    "workspace/${workspace_name}" -n "${namespace}" --timeout=300s >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Bound \
    "pvc/workspace-pvc-${workspace_id}" -n "${namespace}" --timeout=240s >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Bound \
    "pvc/workspace-runtime-home-pvc-${workspace_id}" \
    -n "${namespace}" --timeout=240s >/dev/null
}

deployment_name() {
  component="$1"
  printf '%s-%s' "${component}" "${workspace_id}"
}

pod_name() {
  component="$1"
  kube get pod -n "${namespace}" \
    -l "aileron.io/workspace-id=${workspace_id},aileron.io/component=${component}" \
    --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1].metadata.name}'
}

pod_uid() {
  component="$1"
  name="$(pod_name "${component}")"
  kube get pod "${name}" -n "${namespace}" -o jsonpath='{.metadata.uid}'
}

pod_node() {
  component="$1"
  name="$(pod_name "${component}")"
  kube get pod "${name}" -n "${namespace}" -o jsonpath='{.spec.nodeName}'
}

generation_uids() {
  printf '%s %s %s\n' \
    "$(pod_uid workspace-runtime)" \
    "$(pod_uid workspace-browser)" \
    "$(pod_uid workspace-canvas)"
}

generation_names() {
  printf '%s %s %s\n' \
    "$(pod_name workspace-runtime)" \
    "$(pod_name workspace-browser)" \
    "$(pod_name workspace-canvas)"
}

start_generation_transition_watch() {
  transition="$1"
  [ -z "${generation_watch_pid}" ] || fail "generation transition watch is already active"
  generation_watch_file="${render_dir}/${transition}-pod-watch.tsv"
  generation_watch_error_file="${render_dir}/${transition}-pod-watch.err"
  generation_watch_raw_file="${render_dir}/${transition}-pod-watch.jsonl"
  generation_label_selector="aileron.io%2Fworkspace-id%3D${workspace_id}"
  generation_snapshot_url="/api/v1/namespaces/${namespace}/pods?labelSelector=${generation_label_selector}"
  expected_snapshot_url="/api/v1/namespaces/${namespace}/pods?labelSelector=aileron.io%2Fworkspace-id%3D${workspace_id}"
  [ "${generation_snapshot_url}" = "${expected_snapshot_url}" ] || \
    fail "generation transition raw LIST URL lost its encoded selector"
  generation_snapshot_raw_file="${render_dir}/${transition}-pod-list-snapshot.json"
  kube get --raw "${generation_snapshot_url}" > "${generation_snapshot_raw_file}"
  jq -e --arg workspace_id "${workspace_id}" '
    .kind == "PodList" and
    (.metadata.resourceVersion | (type == "string" and length > 0)) and
    (.items | type == "array") and
    all(.items[]; .metadata.labels["aileron.io/workspace-id"] == $workspace_id)
  ' "${generation_snapshot_raw_file}" >/dev/null || \
    fail "generation transition raw LIST returned an invalid or unscoped PodList"
  start_resource_version="$(jq -er \
    '.metadata.resourceVersion | select(type == "string" and length > 0)' \
    "${generation_snapshot_raw_file}")"
  [ -n "${start_resource_version}" ] || fail "generation transition snapshot has no resourceVersion"
  printf '%s\t%s\n' "${transition}" "${generation_snapshot_url}" \
    >> "${artifact_dir}/generation-list-request.tsv"
  jq -r --arg transition "${transition}" '
    .metadata.resourceVersion as $collection_resource_version |
    .items[] |
    [
      $transition,
      $collection_resource_version,
      .metadata.name,
      .metadata.uid,
      .metadata.resourceVersion,
      (.metadata.labels["aileron.io/component"] // ""),
      (.metadata.annotations["aileron.io/runtime-instance-id"] // "")
    ] |
    @tsv
  ' "${generation_snapshot_raw_file}" >> "${artifact_dir}/generation-list-snapshot.tsv"
  : > "${generation_watch_file}"
  : > "${generation_watch_error_file}"
  : > "${generation_watch_raw_file}"
  printf '%s\t%s\n' "${transition}" "${start_resource_version}" \
    >> "${artifact_dir}/generation-watch-start-resource-version.tsv"
  generation_watch_url="/api/v1/namespaces/${namespace}/pods?watch=1&allowWatchBookmarks=true&resourceVersion=${start_resource_version}&labelSelector=${generation_label_selector}"
  expected_watch_url="/api/v1/namespaces/${namespace}/pods?watch=1&allowWatchBookmarks=true&resourceVersion=${start_resource_version}&labelSelector=aileron.io%2Fworkspace-id%3D${workspace_id}"
  [ "${generation_watch_url}" = "${expected_watch_url}" ] || \
    fail "generation transition raw watch URL lost its snapshot resourceVersion or encoded selector"
  printf '%s\t%s\n' "${transition}" "${generation_watch_url}" \
    >> "${artifact_dir}/generation-watch-request.tsv"
  if command -v kubectl >/dev/null 2>&1; then
    kubectl get --raw "${generation_watch_url}" \
      > "${generation_watch_raw_file}" 2> "${generation_watch_error_file}" &
  else
    k3s kubectl get --raw "${generation_watch_url}" \
      > "${generation_watch_raw_file}" 2> "${generation_watch_error_file}" &
  fi
  generation_watch_pid=$!
  sleep 1
  kill -0 "${generation_watch_pid}" 2>/dev/null || {
    sed -n '1,80p' "${generation_watch_error_file}" >&2
    fail "generation transition watch failed to start: ${transition}"
  }
}

component_status_pod_uid() {
  component="$1"
  case "${component}" in
    workspace-runtime) status_path='{.status.components.runtime.podUid}' ;;
    workspace-browser) status_path='{.status.components.browser.podUid}' ;;
    workspace-canvas) status_path='{.status.components.canvas.podUid}' ;;
    *) fail "unknown managed component: ${component}" ;;
  esac
  kube get workspace "${workspace_name}" -n "${namespace}" -o jsonpath="${status_path}"
}

finish_generation_transition_watch() {
  transition="$1"
  old_uids="$2"
  old_names="$3"
  desired_instance="$4"
  old_runtime_uid="${old_uids%% *}"
  stable_uids="${old_uids#* }"
  old_runtime_name="${old_names%% *}"
  stable_names="${old_names#* }"
  [ -n "${generation_watch_pid}" ] || fail "generation transition watch is not active"

  sleep 2
  kill -0 "${generation_watch_pid}" 2>/dev/null || {
    set +e
    wait "${generation_watch_pid}" 2>/dev/null
    watch_exit_code=$?
    set -e
    generation_watch_pid=""
    sed -n '1,80p' "${generation_watch_error_file}" >&2
    fail "generation transition raw watch exited early with ${watch_exit_code}: ${transition}"
  }
  kill "${generation_watch_pid}" >/dev/null 2>&1 || \
    fail "generation transition raw watch could not be terminated: ${transition}"
  set +e
  wait "${generation_watch_pid}" 2>/dev/null
  watch_exit_code=$?
  set -e
  generation_watch_pid=""
  [ "${watch_exit_code}" -eq 143 ] || \
    fail "generation transition raw watch exit code was ${watch_exit_code}, expected 143: ${transition}"
  [ ! -s "${generation_watch_error_file}" ] || {
    sed -n '1,80p' "${generation_watch_error_file}" >&2
    fail "generation transition raw watch wrote stderr: ${transition}"
  }
  printf '%s\t%s\t0\n' "${transition}" "${watch_exit_code}" \
    >> "${artifact_dir}/generation-watch-process.tsv"
  if jq -e 'select(.type == "ERROR")' "${generation_watch_raw_file}" >/dev/null 2>&1; then
    fail "generation transition raw watch returned an ERROR event: ${transition}"
  fi
  jq_error_file="${render_dir}/${transition}-pod-watch-jq.err"
  jq -r '
    select(.type != "BOOKMARK") |
    [
      .type,
      .object.metadata.name,
      .object.metadata.uid,
      .object.metadata.resourceVersion,
      (.object.metadata.labels["aileron.io/component"] // ""),
      (.object.metadata.annotations["aileron.io/runtime-instance-id"] // "")
    ] |
    @tsv
  ' "${generation_watch_raw_file}" \
    > "${generation_watch_file}" 2> "${jq_error_file}" || {
      sed -n '1,80p' "${jq_error_file}" >&2
      fail "generation transition raw watch JSON could not be parsed: ${transition}"
    }
  [ ! -s "${jq_error_file}" ] || {
    sed -n '1,80p' "${jq_error_file}" >&2
    fail "generation transition raw watch parser wrote stderr: ${transition}"
  }
  [ -s "${generation_watch_file}" ] || fail "generation transition watch produced no events: ${transition}"
  awk -F '\t' 'NF != 6 || $4 == "" {exit 1}' "${generation_watch_file}" || \
    fail "generation transition watch event is missing metadata.resourceVersion: ${transition}"

  first_desired_line="$(awk -F '\t' -v instance="${desired_instance}" \
    '$1 == "ADDED" && $6 == instance {print NR; exit}' "${generation_watch_file}")"
  [ -n "${first_desired_line}" ] || fail "desired generation Pod ADDED event was not observed: ${transition}"
  component="workspace-runtime"
    desired_event_rows="$(awk -F '\t' -v instance="${desired_instance}" -v component="${component}" \
      '$1 == "ADDED" && $5 == component && $6 == instance {print $3 "\t" $4}' \
      "${generation_watch_file}")"
    desired_event_count="$(printf '%s\n' "${desired_event_rows}" | awk 'NF {count++} END {print count+0}')"
    [ "${desired_event_count}" -eq 1 ] || \
      fail "desired ${component} ADDED event count was ${desired_event_count}: ${transition}"
    desired_added_uid="${desired_event_rows%%	*}"
    desired_added_resource_version="${desired_event_rows#*	}"
    final_uid="$(pod_uid "${component}")"
    status_uid="$(component_status_pod_uid "${component}")"
    [ "${desired_added_uid}" = "${final_uid}" ] || \
      fail "desired ${component} ADDED UID does not match final Pod UID: ${transition}"
    [ "${desired_added_uid}" = "${status_uid}" ] || \
      fail "desired ${component} ADDED UID does not match Workspace status UID: ${transition}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${transition}" "${component}" "${desired_instance}" \
      "${desired_added_resource_version}" "${desired_added_uid}" "${final_uid}" "${status_uid}" \
      >> "${artifact_dir}/generation-final-uid-binding.tsv"

  deleted_line="$(awk -F '\t' -v uid="${old_runtime_uid}" \
    '$1 == "DELETED" && $3 == uid {print NR; exit}' "${generation_watch_file}")"
  [ -n "${deleted_line}" ] || \
    fail "old Runtime Pod UID DELETED event was not observed: ${old_runtime_uid}"
  [ "${deleted_line}" -lt "${first_desired_line}" ] || \
    fail "desired generation appeared before old Runtime Pod UID deletion: ${old_runtime_uid}"
  printf '%s\tdeleted-before-%s-desired-added\n' "${old_runtime_uid}" "${transition}" \
    >> "${artifact_dir}/pod-uid-absence.tsv"

  deleted_line="$(awk -F '\t' -v name="${old_runtime_name}" \
    '$1 == "DELETED" && $2 == name {print NR; exit}' "${generation_watch_file}")"
  [ -n "${deleted_line}" ] || \
    fail "old Runtime Pod name DELETED event was not observed: ${old_runtime_name}"
  [ "${deleted_line}" -lt "${first_desired_line}" ] || \
    fail "desired generation appeared before old Runtime Pod name deletion: ${old_runtime_name}"
  printf '%s\tdeleted-before-%s-desired-added\n' "${old_runtime_name}" "${transition}" \
    >> "${artifact_dir}/pod-name-absence.tsv"

  stable_browser_uid="${stable_uids%% *}"
  stable_canvas_uid="${stable_uids#* }"
  stable_browser_name="${stable_names%% *}"
  stable_canvas_name="${stable_names#* }"
  for component in workspace-browser workspace-canvas; do
    lifecycle_event_count="$(awk -F '\t' -v component="${component}" \
      '($1 == "ADDED" || $1 == "DELETED") && $5 == component {count++} END {print count+0}' \
      "${generation_watch_file}")"
    [ "${lifecycle_event_count}" -eq 0 ] || \
      fail "${component} unexpectedly recycled during Runtime generation transition: ${transition}"
  done
  [ "$(pod_uid workspace-browser)" = "${stable_browser_uid}" ] || \
    fail "Browser Pod UID changed during Runtime generation transition: ${transition}"
  [ "$(pod_uid workspace-canvas)" = "${stable_canvas_uid}" ] || \
    fail "Canvas Pod UID changed during Runtime generation transition: ${transition}"
  [ "$(pod_name workspace-browser)" = "${stable_browser_name}" ] || \
    fail "Browser Pod name changed during Runtime generation transition: ${transition}"
  [ "$(pod_name workspace-canvas)" = "${stable_canvas_name}" ] || \
    fail "Canvas Pod name changed during Runtime generation transition: ${transition}"

  awk -F '\t' -v OFS='\t' -v transition="${transition}" \
    '{print transition, NR, $0}' "${generation_watch_file}" \
    >> "${artifact_dir}/generation-transition-watch.tsv"
  generation_watch_file=""
  generation_watch_error_file=""
  generation_watch_raw_file=""
}

replacement_runtime_pod_available() {
  old_uid="$1"
  current_uid="$(kube get pods -n "${namespace}" \
    -l "aileron.io/workspace-id=${workspace_id},aileron.io/component=workspace-runtime" \
    --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1].metadata.uid}' 2>/dev/null || true)"
  [ -n "${current_uid}" ] && [ "${current_uid}" != "${old_uid}" ]
}

wait_generation() {
  expected_instance="$1"
  expected_mount_revision="$2"
  expected_access_revision="$3"
  attempts=300
  while [ "${attempts}" -gt 0 ]; do
    if kube get workspace "${workspace_name}" -n "${namespace}" -o json 2>/dev/null | \
      jq -e \
        --arg instance "${expected_instance}" \
        --argjson mount_revision "${expected_mount_revision}" \
        --argjson access_revision "${expected_access_revision}" '
          .status.phase == "Running"
          and .status.observedGeneration == .metadata.generation
          and .spec.runtime.instanceId == $instance
          and .spec.runtime.mountRevision == $mount_revision
          and .spec.runtime.accessRevision == $access_revision
          and .status.components.runtime.mountObservedRevision == $mount_revision
          and .status.components.runtime.accessObservedRevision == $access_revision
          and .status.components.runtime.observedRevision == .spec.runtime.revision
          and .status.components.browser.observedRevision == .spec.browser.revision
          and .status.components.canvas.observedRevision == .spec.canvas.revision
        ' >/dev/null; then
      status_uids="$(kube get workspace "${workspace_name}" -n "${namespace}" \
        -o jsonpath='{.status.components.runtime.podUid}{" "}{.status.components.browser.podUid}{" "}{.status.components.canvas.podUid}')"
      status_readiness="$(kube get workspace "${workspace_name}" -n "${namespace}" \
        -o jsonpath='{.status.components.runtime.ready}{" "}{.status.components.runtime.terminalReady}{" "}{.status.components.browser.ready}{" "}{.status.components.canvas.ready}')"
      [ "${status_readiness}" = "true true true true" ] || {
        attempts=$((attempts - 1))
        sleep 1
        continue
      }
      for component in workspace-runtime workspace-browser workspace-canvas; do
        name="$(pod_name "${component}")"
        kube wait --for=condition=Ready "pod/${name}" -n "${namespace}" --timeout=30s >/dev/null
      done
      [ "${status_uids}" = "$(generation_uids)" ] && return 0
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  fail "generation did not converge to ${expected_instance}"
}

record_generation() {
  label="$1"
  instance="$2"
  mount_revision="$3"
  access_revision="$4"
  for component in workspace-runtime workspace-browser workspace-canvas; do
    name="$(pod_name "${component}")"
    uid="$(kube get pod "${name}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
    node="$(kube get pod "${name}" -n "${namespace}" -o jsonpath='{.spec.nodeName}')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${label}" "${instance}" "${mount_revision}" "${access_revision}" \
      "${component}" "${name}" "${uid}" "${node}" \
      >> "${artifact_dir}/pod-generations.tsv"
  done
}

assert_same_generation_pod_recreate_refreshes_status() {
  old_name="$(pod_name workspace-runtime)"
  old_uid="$(pod_uid workspace-runtime)"
  runtime_deployment="$(deployment_name workspace-runtime)"
  deployment_generation_before="$(kube get deployment "${runtime_deployment}" -n "${namespace}" \
    -o jsonpath='{.metadata.generation}')"

  kube delete pod "${old_name}" -n "${namespace}" --wait=false >/dev/null
  wait_until "same-generation Runtime Pod replacement" \
    replacement_runtime_pod_available "${old_uid}"
  wait_generation "${instance_1}" 0 0

  new_name="$(pod_name workspace-runtime)"
  new_uid="$(pod_uid workspace-runtime)"
  deployment_generation_after="$(kube get deployment "${runtime_deployment}" -n "${namespace}" \
    -o jsonpath='{.metadata.generation}')"
  status_uid="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.status.components.runtime.podUid}')"

  [ "${old_name}" != "${new_name}" ] || fail "same-generation Runtime Pod name was reused"
  [ "${old_uid}" != "${new_uid}" ] || fail "same-generation Runtime Pod UID was reused"
  [ "${deployment_generation_before}" = "${deployment_generation_after}" ] || \
    fail "Runtime Deployment generation changed during Pod-only replacement"
  [ "${status_uid}" = "${new_uid}" ] || fail "Workspace status did not refresh replacement Runtime Pod UID"
  wait_until "old same-generation Runtime Pod UID ${old_uid} removal" pod_uid_absent "${old_uid}"
  wait_until "old same-generation Runtime Pod name ${old_name} removal" pod_name_absent "${old_name}"

  {
    printf 'component\told_pod_name\told_pod_uid\tnew_pod_name\tnew_pod_uid\tstatus_pod_uid\tdeployment_generation_before\tdeployment_generation_after\n'
    printf 'workspace-runtime\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${old_name}" "${old_uid}" "${new_name}" "${new_uid}" "${status_uid}" \
      "${deployment_generation_before}" "${deployment_generation_after}"
  } > "${artifact_dir}/same-generation-pod-recreate-status-refresh.tsv"
  printf '%s\tabsent-after-same-generation-recreate\n' "${old_uid}" \
    >> "${artifact_dir}/pod-uid-absence.tsv"
  printf '%s\tabsent-after-same-generation-recreate\n' "${old_name}" \
    >> "${artifact_dir}/pod-name-absence.tsv"
  same_generation_status_refresh_verified="true"
}

deployment_stability_snapshot() {
  for component in workspace-runtime workspace-browser workspace-canvas; do
    deployment="$(deployment_name "${component}")"
    values="$(kube get deployment "${deployment}" -n "${namespace}" \
      -o jsonpath='{.metadata.generation}{"\t"}{.status.observedGeneration}{"\t"}{.metadata.resourceVersion}')"
    printf '%s\t%s\n' "${component}" "${values}"
  done
}

assert_deployments_stable() {
  before="$(deployment_stability_snapshot)"
  printf '%s\n' "${before}" | awk -F '\t' 'NF != 4 || $2 != $3 {exit 1}' || \
    fail "managed Deployment observedGeneration did not converge"
  sleep 15
  after="$(deployment_stability_snapshot)"
  [ "${before}" = "${after}" ] || fail "managed Deployment generation or resourceVersion was not stable"

  {
    printf 'sample\tcomponent\tgeneration\tobserved_generation\tresource_version\n'
    printf '%s\n' "${before}" | awk 'BEGIN {OFS="\t"} {print "before", $0}'
    printf '%s\n' "${after}" | awk 'BEGIN {OFS="\t"} {print "after", $0}'
  } > "${artifact_dir}/deployment-stability.tsv"
  deployment_stability_verified="true"
}

workspace_runtime_status_is_reconciling_without_uid() {
  phase="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  status_uid="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.status.components.runtime.podUid}' 2>/dev/null || true)"
  [ "${phase}" = "Reconciling" ] && [ -z "${status_uid}" ]
}

assert_isolated_pod_watch_pipeline() {
  runtime_uid="$(pod_uid workspace-runtime)"
  deployment_before="$(deployment_stability_snapshot)"
  workspace_rv_before="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.metadata.resourceVersion}')"

  cat > "${render_dir}/pod-watch-sentinel.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: pod-watch-sentinel
  namespace: ${namespace}
  labels:
    aileron.io/workspace-id: ${workspace_id}
    aileron.io/component: workspace-runtime
  annotations:
    aileron.io/component-revision: "1"
    aileron.io/component-instance-id: ${instance_1}
    aileron.io/runtime-instance-id: ${instance_1}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_a}
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: sentinel
      image: ${workload_probe_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args: ["exec sleep 3600"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/pod-watch-sentinel.yaml" >/dev/null
  sentinel_uid="$(kube get pod pod-watch-sentinel -n "${namespace}" -o jsonpath='{.metadata.uid}')"
  sentinel_owner_reference_count="$(kube get pod pod-watch-sentinel -n "${namespace}" -o json | \
    jq -er '(.metadata.ownerReferences // []) | length')"
  [ "${sentinel_owner_reference_count}" -eq 0 ] || \
    fail "isolated Pod watch sentinel unexpectedly has an ownerReference"
  wait_until "isolated Pod watch status transition" \
    workspace_runtime_status_is_reconciling_without_uid

  workspace_rv_reconciling="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.metadata.resourceVersion}')"
  deployment_reconciling="$(deployment_stability_snapshot)"
  [ "${deployment_before}" = "${deployment_reconciling}" ] || \
    fail "Deployment changed during isolated Pod watch status transition"
  [ "${workspace_rv_before}" != "${workspace_rv_reconciling}" ] || \
    fail "Workspace resourceVersion did not change after isolated Pod event"

  kube delete pod pod-watch-sentinel -n "${namespace}" --wait=true >/dev/null
  wait_generation "${instance_1}" 0 0
  workspace_rv_restored="$(kube get workspace "${workspace_name}" -n "${namespace}" \
    -o jsonpath='{.metadata.resourceVersion}')"
  deployment_restored="$(deployment_stability_snapshot)"
  [ "${deployment_before}" = "${deployment_restored}" ] || \
    fail "Deployment changed while isolated Pod watch status was restored"
  [ "$(pod_uid workspace-runtime)" = "${runtime_uid}" ] || \
    fail "managed Runtime Pod changed during isolated Pod watch test"

  {
    printf 'workspace_rv_before\tworkspace_rv_reconciling\tworkspace_rv_restored\tmanaged_runtime_pod_uid\tsentinel_pod_uid\tsentinel_owner_reference_count\n'
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${workspace_rv_before}" "${workspace_rv_reconciling}" "${workspace_rv_restored}" \
      "${runtime_uid}" "${sentinel_uid}" "${sentinel_owner_reference_count}"
    printf '\nsample\tcomponent\tgeneration\tobserved_generation\tresource_version\n'
    printf '%s\n' "${deployment_before}" | awk 'BEGIN {OFS="\t"} {print "before", $0}'
    printf '%s\n' "${deployment_reconciling}" | awk 'BEGIN {OFS="\t"} {print "reconciling", $0}'
    printf '%s\n' "${deployment_restored}" | awk 'BEGIN {OFS="\t"} {print "restored", $0}'
  } > "${artifact_dir}/isolated-pod-watch-status-refresh.tsv"
  printf '%s\tabsent-after-isolated-pod-watch\n' "${sentinel_uid}" \
    >> "${artifact_dir}/pod-uid-absence.tsv"
  printf 'pod-watch-sentinel\tabsent-after-isolated-pod-watch\n' \
    >> "${artifact_dir}/pod-name-absence.tsv"
  pod_watch_pipeline_verified="true"
}

pod_uid_absent() {
  old_uid="$1"
  ! kube get pods -n "${namespace}" \
    -o custom-columns=UID:.metadata.uid --no-headers 2>/dev/null | grep -Fxq "${old_uid}"
}

pod_name_absent() {
  old_name="$1"
  ! kube get pod "${old_name}" -n "${namespace}" >/dev/null 2>&1
}

runtime_scoped_secrets_isolated() {
  runtime_deployment="$(deployment_name workspace-runtime)"
  kube get deployment "${runtime_deployment}" -n "${namespace}" -o json | \
    jq -e \
      --arg secret_name "${runtime_secret_name}" '
        ([.spec.template.spec.containers[]
          | select(.name == "runtime")
          | .env[]?.name
          | select(
              . == "DATABASE_URL"
              or . == "REDIS_URL"
              or . == "INTERNAL_API_TOKEN"
              or . == "MANAGER_CONTROL_ASSERTION"
              or . == "RUNTIME_CONTROL_TOKEN"
              or . == "MANAGER_URL"
              or . == "PLATFORM_MANAGER_URL"
            )]
        | length) == 0
        and ([.spec.template.spec.containers[]
          | select(.name == "runtime")
          | .env[]?
          | select(.name == "AILERON_RUNTIME_DATABASE_CONNECTION_FILE")][0].value
            == "/etc/aileron/runtime-secrets/runtime-database-connection")
        and ([.spec.template.spec.containers[]
          | select(.name == "runtime")
          | .env[]?
          | select(.name == "AILERON_RUNTIME_CONTROL_TOKEN_FILE")][0].value
            == "/etc/aileron/runtime-secrets/runtime-control-token")
        and ([.spec.template.spec.containers[]
          | select(.name == "runtime")
          | .volumeMounts[]?
          | select(.name == "runtime-secrets")][0]
            == {name: "runtime-secrets", mountPath: "/etc/aileron/runtime-secrets", readOnly: true})
        and ([.spec.template.spec.volumes[]
          | select(.name == "runtime-secrets")][0].secret
            == {
              secretName: $secret_name,
              defaultMode: 288,
              items: [
                {key: "runtime-database-connection", path: "runtime-database-connection", mode: 288},
                {key: "runtime-control-token", path: "runtime-control-token", mode: 288}
              ]
            })
        and ((.spec.template.metadata.annotations // {})
          | has("aileron.io/internal-api-token-revision") | not)
      ' >/dev/null
}

assert_runtime_scoped_secrets_isolated() {
  runtime_deployment="$(deployment_name workspace-runtime)"
  wait_until "Runtime scoped secret isolation" runtime_scoped_secrets_isolated
  kube get workspace "${workspace_name}" -n "${namespace}" -o json | \
    jq -e --arg secret_name "${runtime_secret_name}" '
      .spec.runtime.runtimeSecretName == $secret_name
      and (.spec.runtime | has("controlAssertion") | not)
    ' >/dev/null || fail "Workspace CR exposes the wrong Runtime secret contract"
  kube get deployment "${runtime_deployment}" -n "${namespace}" -o json | \
    jq '{
      deployment: .metadata.name,
      runtimeScopedSecretFiles: ([
        .spec.template.spec.containers[]
        | select(.name == "runtime")
        | .env[]?
        | select(.name == "AILERON_RUNTIME_DATABASE_CONNECTION_FILE" or .name == "AILERON_RUNTIME_CONTROL_TOKEN_FILE")
        | {name, path: .value}
      ] | sort),
      runtimeScopedSecretVolume: ([
        .spec.template.spec.volumes[]
        | select(.name == "runtime-secrets")
        | .secret
      ][0]),
      hasInternalTokenRevisionAnnotation: ((.spec.template.metadata.annotations // {})
        | has("aileron.io/internal-api-token-revision"))
    }' > "${artifact_dir}/runtime-scoped-secret-isolation.json"
  runtime_scoped_secrets_isolated_verified="true"
}

spread_workloads() {
  runtime_deployment="$(deployment_name workspace-runtime)"
  browser_deployment="$(deployment_name workspace-browser)"
  canvas_deployment="$(deployment_name workspace-canvas)"
  kube patch deployment "${runtime_deployment}" -n "${namespace}" --type=merge \
    -p "{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":{\"kubernetes.io/hostname\":\"${node_a}\"}}}}}" >/dev/null
  for deployment in "${browser_deployment}" "${canvas_deployment}"; do
    kube patch deployment "${deployment}" -n "${namespace}" --type=merge \
      -p "{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":{\"kubernetes.io/hostname\":\"${node_b}\"}}}}}" >/dev/null
  done
  kube rollout status deployment/"${runtime_deployment}" -n "${namespace}" --timeout=240s >/dev/null
  kube rollout status deployment/"${browser_deployment}" -n "${namespace}" --timeout=240s >/dev/null
  kube rollout status deployment/"${canvas_deployment}" -n "${namespace}" --timeout=240s >/dev/null
  wait_generation "${instance_1}" 0 0

  [ "$(pod_node workspace-runtime)" = "${node_a}" ] || fail "Runtime did not schedule on node A"
  [ "$(pod_node workspace-browser)" = "${node_b}" ] || fail "Browser did not schedule on node B"
  [ "$(pod_node workspace-canvas)" = "${node_b}" ] || fail "Canvas did not schedule on node B"
  deployment_watch_status_refresh_verified="true"
}

assert_workspace_rwx() {
  access_modes="$(kube get pvc "workspace-pvc-${workspace_id}" -n "${namespace}" \
    -o jsonpath='{.status.accessModes[*]}')"
  printf '%s\n' "${access_modes}" | grep -qw ReadWriteMany || fail "Workspace PVC is not RWX"

  browser_pod="$(pod_name workspace-browser)"
  runtime_pod="$(pod_name workspace-runtime)"
  canvas_pod="$(pod_name workspace-canvas)"
  kube exec -n "${namespace}" "${browser_pod}" -- \
    /bin/sh -ec "printf '%s\\n' cross-node > /workspace/cross-node"
  kube exec -n "${namespace}" "${runtime_pod}" -- grep -qx cross-node /workspace/cross-node
  kube exec -n "${namespace}" "${canvas_pod}" -- grep -qx cross-node /workspace/cross-node
  workspace_rwx_verified="true"
}

assert_runtime_home_contract() {
  runtime_pvc="workspace-runtime-home-pvc-${workspace_id}"
  runtime_deployment="$(deployment_name workspace-runtime)"
  runtime_pod="$(pod_name workspace-runtime)"
  runtime_home_marker=".aileron-runtime-home-e2e"
  runtime_home_token="runtime-home-${run_id}"

  access_modes="$(kube get pvc "${runtime_pvc}" -n "${namespace}" \
    -o jsonpath='{.status.accessModes[*]}')"
  printf '%s\n' "${access_modes}" | grep -qw "${runtime_home_access_mode}" || \
    fail "Runtime HOME PVC does not use ${runtime_home_access_mode}"

  kube get deployment "${runtime_deployment}" -n "${namespace}" -o json | jq -e \
    --arg pvc "${runtime_pvc}" '
      any(.spec.template.spec.volumes[]?;
        .name == "runtime-home" and .persistentVolumeClaim.claimName == $pvc)
      and any(.spec.template.spec.containers[0].volumeMounts[]?;
        .name == "runtime-home" and .mountPath == "/home/developer")
      and any(.spec.template.spec.containers[0].env[]?;
        .name == "HOME" and .value == "/home/developer")
      and all(.spec.template.spec.containers[0].volumeMounts[]?;
        .mountPath != "/runtime-state")
    ' >/dev/null || fail "Runtime Deployment HOME mount contract is invalid"

  # Expand HOME inside the Runtime Pod instead of on the E2E runner.
  # shellcheck disable=SC2016
  kube exec -n "${namespace}" "${runtime_pod}" -- /bin/sh -ec \
    'test "${HOME}" = /home/developer
     printf "%s\n" "$1" > "${HOME}/$2"
     test -f "${HOME}/$2"' \
    -- "${runtime_home_token}" "${runtime_home_marker}"

  kube get pvc "${runtime_pvc}" -n "${namespace}" -o yaml \
    > "${artifact_dir}/runtime-home-pvc.yaml"
  kube get deployment "${runtime_deployment}" -n "${namespace}" -o yaml \
    > "${artifact_dir}/runtime-home-deployment.yaml"
}

assert_runtime_home_persists_after_recreate() {
  runtime_pod="$(pod_name workspace-runtime)"
  kube exec -n "${namespace}" "${runtime_pod}" -- \
    grep -qx "runtime-home-${run_id}" \
    "/home/developer/.aileron-runtime-home-e2e" || \
    fail "Runtime HOME marker did not survive Pod recreation"
  runtime_home_persistence_verified="true"
}

assert_runtime_mount() {
  alias="$1"
  expected="$2"
  runtime_pod="$(pod_name workspace-runtime)"
  manager_node="$(kube get pod manager-writer -n "${namespace}" -o jsonpath='{.spec.nodeName}')"
  runtime_node="$(kube get pod "${runtime_pod}" -n "${namespace}" -o jsonpath='{.spec.nodeName}')"
  [ "${manager_node}" != "${runtime_node}" ] || \
    fail "Manager writer and Runtime were not spread across nodes"
  runtime_uid="$(kube exec -n "${namespace}" "${runtime_pod}" -- id -u)"
  [ "${runtime_uid}" -ne 0 ] || fail "Runtime Pod is running as root"
  kube exec -n "${namespace}" "${runtime_pod}" -- \
    grep -qx "${expected}" "/knowledge/${alias}/fixture.txt"
  probe_evidence="${artifact_dir}/runtime-ro-${alias}-${expected}.txt"
  {
    printf 'manager_node=%s\n' "${manager_node}"
    printf 'runtime_node=%s\n' "${runtime_node}"
    kube exec -n "${namespace}" "${runtime_pod}" -- id
    kube exec -n "${namespace}" "${runtime_pod}" -- \
      cat "/knowledge/${alias}/fixture.txt"
  } > "${probe_evidence}"
  if kube exec -n "${namespace}" "${runtime_pod}" -- \
    /bin/sh -ec "touch '/knowledge/${alias}/.write-probe'" \
    >> "${probe_evidence}" 2>&1; then
    fail "Runtime Knowledge Base mount is writable: ${alias}"
  fi
  kube exec -n "${namespace}" "${runtime_pod}" -- \
    test ! -e "/knowledge/${alias}/.write-probe"
  runtime_ro_verified="true"
  knowledge_base_cross_node_verified="true"
}

workspace_patch_payload() {
  instance="$1"
  mount_revision="$2"
  access_revision="$3"
  knowledge_bases_json="$4"
  printf '%s\n' \
    "{\"spec\":{\"runtime\":{\"instanceId\":\"${instance}\",\"mountRevision\":${mount_revision},\"accessRevision\":${access_revision}},\"knowledgeBases\":${knowledge_bases_json}}}"
}

patch_workspace() {
  patch_payload="$(workspace_patch_payload "$@")"
  kube patch workspace "${workspace_name}" -n "${namespace}" --type=merge \
    -p "${patch_payload}" >/dev/null
}

workspace_mount_contract_snapshot() {
  kube get workspace "${workspace_name}" -n "${namespace}" \
    -o json | \
    jq -ceS '{
      mountRevision: .spec.runtime.mountRevision,
      knowledgeBases: (.spec.knowledgeBases | sort_by(.kbId, .alias))
    }'
}

workspace_access_patch_payload() {
  instance="$1"
  access_revision="$2"
  printf '%s\n' \
    "{\"spec\":{\"runtime\":{\"instanceId\":\"${instance}\",\"accessRevision\":${access_revision}}}}"
}

patch_workspace_access_only() {
  access_patch="$(workspace_access_patch_payload "$@")"
  printf '%s\n' "${access_patch}" | \
    jq -e '
      (keys == ["spec"]) and
      ((.spec | keys) == ["runtime"]) and
      ((.spec.runtime | keys) == ["accessRevision", "instanceId"])
    ' >/dev/null || fail "access-only patch contains fields outside the access recycle contract"
  printf '%s\n' "${access_patch}" > "${artifact_dir}/access-only-patch.json"
  kube patch workspace "${workspace_name}" -n "${namespace}" --type=merge \
    -p "${access_patch}" >/dev/null
}

render_workspace_contract_fixtures() {
  output_dir="$1"
  mkdir -p "${output_dir}"
  render_workspace_manifest "${output_dir}/workspace.yaml"
  workspace_patch_payload "${instance_2}" 1 0 \
    "[{\"kbId\":\"${kb_id}\",\"alias\":\"product\"}]" \
    > "${output_dir}/mount-patch.json"
  workspace_access_patch_payload "${instance_3}" 1 \
    > "${output_dir}/access-patch.json"
}

update_fixture_as_uid_b() {
  updater_fs_group="$(render_fs_group_block '    ')"
  cat > "${render_dir}/manager-updater.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: manager-updater
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_b}
  securityContext:
    runAsNonRoot: true
    runAsUser: ${uid_b}
    runAsGroup: ${uid_b}
    seccompProfile:
      type: RuntimeDefault
${updater_fs_group}
  containers:
    - name: manager-updater
      image: ${manager_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args:
        - |
          test "\$(id -u)" = "${uid_b}"
          root_gid="\$(stat -c '%g' /knowledge-bases)"
          id -G | tr ' ' '\n' | grep -qx "\${root_gid}"
          umask 0007
          printf '%s\n' fixture-v2 > "/knowledge-bases/${kb_id}/.fixture.next"
          mv "/knowledge-bases/${kb_id}/.fixture.next" "/knowledge-bases/${kb_id}/fixture.txt"
          printf '%s\n' "${uid_b}" > /state/uid-transition
          test "\$(stat -c '%g' "/knowledge-bases/${kb_id}/fixture.txt")" = "\${root_gid}"
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      volumeMounts:
        - name: knowledge-bases
          mountPath: /knowledge-bases
        - name: manager-state
          mountPath: /state
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: knowledge-bases
      persistentVolumeClaim:
        claimName: knowledge-bases-pvc
    - name: manager-state
      persistentVolumeClaim:
        claimName: manager-state-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube apply -f "${render_dir}/manager-updater.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Succeeded pod/manager-updater \
    -n "${namespace}" --timeout=180s >/dev/null
  kube exec -n "${namespace}" manager-writer -- \
    grep -qx "${uid_b}" /state/uid-transition
  printf 'path\tuid\tgid\n' > "${artifact_dir}/uid-transition.tsv"
  for path in \
    "/knowledge-bases/${kb_id}/fixture.txt" \
    /state/uid-transition; do
    owner="$(kube exec -n "${namespace}" manager-writer -- stat -c '%u %g' "${path}")"
    owner_uid="${owner%% *}"
    owner_gid="${owner#* }"
    printf '%s\t%s\t%s\n' "${path}" "${owner_uid}" "${owner_gid}" \
      >> "${artifact_dir}/uid-transition.tsv"
  done
  uid_transition_verified="true"
}

assert_content_update_without_recreate() {
  before_uids="$(generation_uids)"
  update_started_at="$(date +%s)"
  update_fixture_as_uid_b
  runtime_pod="$(pod_name workspace-runtime)"
  wait_until "updated KB content" kube exec -n "${namespace}" "${runtime_pod}" -- \
    grep -qx fixture-v2 /knowledge/runbook/fixture.txt
  update_visible_at="$(date +%s)"
  after_uids="$(generation_uids)"
  [ "${before_uids}" = "${after_uids}" ] || fail "KB content update recreated the execution plane"
  {
    printf 'before_pod_uids=%s\n' "${before_uids}"
    printf 'after_pod_uids=%s\n' "${after_uids}"
    printf 'visibility_latency_seconds=%s\n' "$((update_visible_at - update_started_at))"
  } > "${artifact_dir}/content-update-without-recreate.txt"
  content_update_verified="true"
}

assert_openshift_admission() {
  [ -n "${expected_scc}" ] || return 0
  cat > "${render_dir}/openshift-restricted-dry-run.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: openshift-restricted-dry-run
  namespace: ${namespace}
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${workload_probe_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec", "exit 0"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
EOF
  kube create --dry-run=server -f "${render_dir}/openshift-restricted-dry-run.yaml" -o yaml \
    > "${artifact_dir}/openshift-server-dry-run.yaml"
  printf 'component\tpod\tscc\teffective_uid\teffective_groups\tfs_group\tselinux_level\n' \
    > "${artifact_dir}/openshift-admission.tsv"
  for component in workspace-runtime workspace-browser workspace-canvas; do
    pod="$(pod_name "${component}")"
    actual_scc="$(kube get pod "${pod}" -n "${namespace}" \
      -o 'go-template={{ index .metadata.annotations "openshift.io/scc" }}')"
    [ "${actual_scc}" = "${expected_scc}" ] || \
      fail "${component} used SCC ${actual_scc}, expected ${expected_scc}"
    selinux_level="$(kube get pod "${pod}" -n "${namespace}" \
      -o jsonpath='{.spec.securityContext.seLinuxOptions.level}')"
    [ -n "${selinux_level}" ] || fail "${component} is missing an injected SELinux level"
    pod_fs_group="$(kube get pod "${pod}" -n "${namespace}" \
      -o jsonpath='{.spec.securityContext.fsGroup}')"
    [ -n "${pod_fs_group}" ] || fail "${component} is missing an effective fsGroup"
    effective_uid="$(kube exec -n "${namespace}" "${pod}" -- id -u)"
    [ "${effective_uid}" -ne 0 ] || fail "${component} was admitted with UID 0"
    effective_groups="$(kube exec -n "${namespace}" "${pod}" -- id -G)"
    printf '%s\n' "${effective_groups}" | tr ' ' '\n' | grep -Fxq "${pod_fs_group}" || \
      fail "${component} process is missing the admitted fsGroup"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${component}" "${pod}" "${actual_scc}" "${effective_uid}" \
      "${effective_groups}" "${pod_fs_group}" "${selinux_level}" \
      >> "${artifact_dir}/openshift-admission.tsv"
  done
  openshift_admission_verified="true"
}

assert_product_hook() {
  [ "${require_product_lifecycle}" = "true" ] || return 0
  hook="${PRODUCT_CONFORMANCE_HOOK:?PRODUCT_CONFORMANCE_HOOK is required}"
  [ -x "${hook}" ] || fail "product conformance hook is not executable: ${hook}"
  capabilities_output="${artifact_dir}/product-capabilities.json"
  product_runtime_image="$(
    resolve_product_workload_image "${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}"
  )"
  product_browser_image="$(
    resolve_product_workload_image "${BROWSER_IMAGE:?BROWSER_IMAGE is required}"
  )"
  product_canvas_image="$(
    resolve_product_workload_image "${CANVAS_IMAGE:?CANVAS_IMAGE is required}"
  )"
  E2E_NAMESPACE="${namespace}" \
  E2E_RUN_ID="${run_id}" \
  E2E_STORAGE_MODE="${storage_mode}" \
  E2E_WORKSPACE_ID="${workspace_id}" \
  E2E_KB_ID="${kb_id}" \
  RWX_STORAGE_CLASS="${storage_class}" \
  RWO_STORAGE_CLASS="${rwo_storage_class}" \
  RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}" \
  RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_access_mode}" \
  E2E_SHARED_STORAGE_SIZE="${shared_storage_size}" \
  E2E_RWO_STORAGE_SIZE="${rwo_storage_size}" \
  E2E_RUNTIME_HOME_STORAGE_SIZE="${runtime_home_storage_size}" \
  NFS_SERVER="${nfs_server}" \
  IMAGE_PULL_POLICY="${image_pull_policy}" \
  IMAGE_PULL_SECRET_NAME="${image_pull_secret_name}" \
  PLATFORM_STORAGE_GID="${storage_gid}" \
  MANAGER_IMAGE="${manager_image}" \
  RUNTIME_IMAGE="${product_runtime_image}" \
  BROWSER_IMAGE="${product_browser_image}" \
  CANVAS_IMAGE="${product_canvas_image}" \
  REDIS_IMAGE="${REDIS_IMAGE:?REDIS_IMAGE is required}" \
  POSTGRES_IMAGE="${POSTGRES_IMAGE:?POSTGRES_IMAGE is required}" \
  PRODUCT_DRIVER_IMAGE="${PRODUCT_DRIVER_IMAGE:?PRODUCT_DRIVER_IMAGE is required}" \
  PRODUCT_DATA_SERVICE_MODE="${PRODUCT_DATA_SERVICE_MODE:-bundled}" \
  PRODUCT_CAPABILITIES_OUTPUT="${capabilities_output}" \
    "${hook}" > "${artifact_dir}/product-conformance.log" 2>&1
  [ -s "${capabilities_output}" ] || fail "product conformance hook did not write capabilities"
  transaction_output="${capabilities_output%.json}-installation-transaction.tsv"
  [ -s "${transaction_output}" ] || \
    fail "product conformance hook did not write installation transaction evidence"
  expected_data_service_mode="${PRODUCT_DATA_SERVICE_MODE:-bundled}"
  awk -F '\t' -v mode="${expected_data_service_mode}" '
    NR == 2 && $1 == mode && $5 == "true" &&
      ((mode == "external" && $6 == "true" && $7 == "true" &&
        $8 == "true" && $9 == "true" && $10 == "true" && $11 == "true" &&
        $12 == "true" && $13 == "true" && $14 == "true") ||
       (mode == "bundled" && $6 == "not-applicable" &&
        $7 == "not-applicable" && $8 == "not-applicable" &&
        $9 == "not-applicable" && $10 == "not-applicable" &&
        $11 == "not-applicable" && $12 == "not-applicable" &&
        $13 == "not-applicable" && $14 == "not-applicable")) {
      found = 1
    }
    END {exit !found}
  ' "${transaction_output}" || fail "product installation transaction evidence is invalid"
  if [ "${expected_data_service_mode}" = "external" ]; then
    identity_output="${capabilities_output%.json}-identity-external-lifecycle.tsv"
    [ -s "${identity_output}" ] || \
      fail "product conformance hook did not write external Identity lifecycle evidence"
    awk -F '\t' '
      NR == 2 && NF == 7 {
        for (field = 1; field <= 7; field++) {
          if ($field != "true") exit 1
        }
        found = 1
      }
      END {exit !found}
    ' "${identity_output}" || fail "external Identity lifecycle evidence is invalid"
  fi
  "${repo_root}/scripts/test/kubernetes/product-conformance/validate-product-report.sh" \
    "${capabilities_output}" || fail "product conformance evidence contract is invalid"
  product_lifecycle_verified="true"
}

snapshot_before_delete() {
  kube get workspace "${workspace_name}" -n "${namespace}" -o yaml \
    > "${artifact_dir}/workspace-before-delete.yaml"
  kube get pods,deployments,services,pvc -n "${namespace}" -o yaml \
    > "${artifact_dir}/workloads-before-delete.yaml"
}

workspace_absent() {
  ! kube get workspace "${workspace_name}" -n "${namespace}" >/dev/null 2>&1
}

managed_pods_absent() {
  [ "$(kube get pods -n "${namespace}" \
    -l "aileron.io/workspace-id=${workspace_id}" --no-headers 2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]
}

workspace_pvc_absent() {
  ! kube get pvc "workspace-pvc-${workspace_id}" -n "${namespace}" >/dev/null 2>&1
}

runtime_home_pvc_absent() {
  ! kube get pvc "workspace-runtime-home-pvc-${workspace_id}" \
    -n "${namespace}" >/dev/null 2>&1
}

delete_workspace_and_assert_absence() {
  old_uids="$(generation_uids)"
  old_names="$(generation_names)"
  snapshot_before_delete
  kube delete workspace "${workspace_name}" -n "${namespace}" --wait=false >/dev/null
  wait_until "Workspace CR deletion" workspace_absent
  for old_uid in ${old_uids}; do
    wait_until "deleted Workspace Pod UID ${old_uid} removal" pod_uid_absent "${old_uid}"
    printf '%s\tabsent-after-workspace-delete\n' "${old_uid}" \
      >> "${artifact_dir}/pod-uid-absence.tsv"
  done
  for old_name in ${old_names}; do
    wait_until "deleted Workspace Pod name ${old_name} removal" pod_name_absent "${old_name}"
    printf '%s\tabsent-after-workspace-delete\n' "${old_name}" \
      >> "${artifact_dir}/pod-name-absence.tsv"
  done
  wait_until "managed Pod deletion" managed_pods_absent
  wait_until "Workspace PVC deletion" workspace_pvc_absent
  wait_until "Runtime HOME PVC deletion" runtime_home_pvc_absent
}

collect_artifacts() {
  mkdir -p "${artifact_dir}"
  {
    printf 'mode=%s\n' "${mode}"
    printf 'storage_mode=%s\n' "${storage_mode}"
    printf 'namespace=%s\n' "${namespace}"
    printf 'storage_class=%s\n' "${storage_class}"
    printf 'rwo_storage_class=%s\n' "${rwo_storage_class}"
    printf 'runtime_home_storage_class=%s\n' "${runtime_home_storage_class}"
    printf 'runtime_home_access_mode=%s\n' "${runtime_home_access_mode}"
    printf 'shared_storage_size=%s\n' "${shared_storage_size}"
    printf 'rwo_storage_size=%s\n' "${rwo_storage_size}"
    printf 'runtime_home_storage_size=%s\n' "${runtime_home_storage_size}"
    printf 'node_a=%s\n' "${node_a}"
    printf 'node_b=%s\n' "${node_b}"
    printf 'storage_gid=%s\n' "${storage_gid}"
    printf 'uid_a=%s\n' "${uid_a}"
    printf 'uid_b=%s\n' "${uid_b}"
  } > "${artifact_dir}/environment.txt"

  kube version -o yaml > "${artifact_dir}/kubernetes-version.yaml" 2>&1 || true
  kube get nodes -o wide > "${artifact_dir}/nodes.txt" 2>&1 || true
  kube get storageclass "${storage_class}" -o yaml \
    > "${artifact_dir}/storage-class.yaml" 2>&1 || true
  kube get csidriver -o yaml > "${artifact_dir}/csi-drivers.yaml" 2>&1 || true
  if [ "${namespace_created}" = "true" ]; then
    kube get all,pvc,workspace -n "${namespace}" -o wide \
      > "${artifact_dir}/namespace-resources.txt" 2>&1 || true
    kube get events -n "${namespace}" --sort-by=.lastTimestamp \
      > "${artifact_dir}/events.txt" 2>&1 || true
    kube logs deployment/workspace-operator -n "${namespace}" \
      > "${artifact_dir}/workspace-operator.log" 2>&1 || true
  fi

  release_verified="false"
  if [ "${mode}" = "platform" ] && [ "${product_lifecycle_verified}" = "true" ] && [ "${result}" = "passed" ]; then
    release_verified="true"
  fi
  cat > "${artifact_dir}/capabilities.json" <<EOF
{
  "result": "${result}",
  "operatorCrdReconcile": ${operator_verified},
  "runtimeScopedSecretsIsolated": ${runtime_scoped_secrets_isolated_verified},
  "managerImageCanonicalWrite": ${manager_write_verified},
  "managerStateWritable": ${manager_write_verified},
  "rwoStatePersistence": ${rwo_state_persistence_verified},
  "storageRootSetgid": ${storage_setgid_verified},
  "wrongStorageGroupRejected": ${storage_negative_verified},
  "nfsRootSquash": ${root_squash_verified},
  "nfsLocking": ${nfs_lock_verified},
  "arbitraryUidTransition": ${uid_transition_verified},
  "runtimeNonRootReadOnlyMount": ${runtime_ro_verified},
  "crossNodeKnowledgeBaseRead": ${knowledge_base_cross_node_verified},
  "crossNodeWorkspaceRwx": ${workspace_rwx_verified},
  "runtimeHomePersistence": ${runtime_home_persistence_verified},
  "generationPodUidFencing": ${generation_fencing_verified},
  "generationPodNameFencing": ${generation_fencing_verified},
  "generationWatchFinalUidBinding": ${generation_watch_uid_binding_verified},
  "generationWatchProcessValidated": ${generation_watch_process_verified},
  "deploymentWatchStatusRefresh": ${deployment_watch_status_refresh_verified},
  "sameGenerationPodStatusRefresh": ${same_generation_status_refresh_verified},
  "isolatedPodWatchStatusRefresh": ${pod_watch_pipeline_verified},
  "accessOnlyMountContractStable": ${access_only_mount_contract_verified},
  "managedDeploymentGenerationStable": ${deployment_stability_verified},
  "contentUpdateWithoutRecreate": ${content_update_verified},
  "openshiftRestrictedV2Admission": ${openshift_admission_verified},
  "managerApiLifecycle": ${product_lifecycle_verified},
  "durableJobs": ${product_lifecycle_verified},
  "rapidConsecutiveMutations": ${product_lifecycle_verified},
  "reconcileFailureRetry": ${product_lifecycle_verified},
  "startStopRestart": ${product_lifecycle_verified},
  "errorRecovery": ${product_lifecycle_verified},
  "stoppedWorkspace": ${product_lifecycle_verified},
  "actionGate": ${product_lifecycle_verified},
  "signedDrain": ${product_lifecycle_verified},
  "forcedTerminationProof": ${product_lifecycle_verified},
  "oldConnectionRejection": ${product_lifecycle_verified},
  "browserPairing": ${product_lifecycle_verified},
  "certificationEligible": ${release_verified},
  "releaseConformanceVerified": ${release_verified}
}
EOF
  printf '%s\n' "${result}" > "${artifact_dir}/result.txt"
}

cleanup_workspaces_absent() {
  if ! kube get customresourcedefinition \
    workspaces.platform.aileron.io >/dev/null 2>&1; then
    return 0
  fi
  cleanup_workspaces="$(
    kube get workspaces.platform.aileron.io -n "${namespace}" -o name 2>/dev/null
  )" || return 1
  [ -z "${cleanup_workspaces}" ]
}

cleanup_namespace_absent() {
  cleanup_namespace="$(
    kube get namespace "${namespace}" --ignore-not-found -o name 2>/dev/null
  )" || return 1
  [ -z "${cleanup_namespace}" ]
}

cleanup_wait_until() {
  description="$1"
  remaining_seconds="$2"
  shift 2
  while :; do
    if "$@"; then
      return 0
    fi
    [ "${remaining_seconds}" -gt 0 ] || break
    remaining_seconds=$((remaining_seconds - 1))
    sleep 1
  done
  log "Cleanup timed out waiting for ${description}"
  return 1
}

cleanup_test_namespace() {
  [ "${namespace_created}" = "true" ] || return 0
  cleanup_run_id="$(
    kube get namespace "${namespace}" \
      -o jsonpath='{.metadata.labels.aileron\.io/test-run-id}' 2>/dev/null
  )"
  if [ "${cleanup_run_id}" != "${run_id}" ]; then
    log "Refusing to clean namespace ${namespace}: test run label does not match ${run_id}"
    return 1
  fi

  log "Deleting Workspace resources before test namespace ${namespace}"
  kube delete workspaces.platform.aileron.io --all -n "${namespace}" \
    --ignore-not-found --wait=false >/dev/null 2>&1
  if ! cleanup_wait_until "Workspace finalization" 60 cleanup_workspaces_absent; then
    kube get workspaces.platform.aileron.io -n "${namespace}" -o name 2>/dev/null | \
      while IFS= read -r workspace_resource; do
        [ -n "${workspace_resource}" ] || continue
        log "Removing finalizers from disposable test resource ${namespace}/${workspace_resource}"
        kube patch "${workspace_resource}" -n "${namespace}" --type=merge \
          -p '{"metadata":{"finalizers":[]}}' >/dev/null 2>&1
      done
    cleanup_wait_until "forced Workspace finalization" 15 cleanup_workspaces_absent || true
  fi

  kube delete namespace "${namespace}" --wait=false >/dev/null 2>&1
  cleanup_wait_until "test namespace deletion" 120 cleanup_namespace_absent || true
}

cleanup() {
  exit_code=$?
  trap - EXIT HUP INT TERM
  set +e
  if [ -n "${generation_watch_pid}" ]; then
    kill "${generation_watch_pid}" >/dev/null 2>&1 || true
    wait "${generation_watch_pid}" 2>/dev/null || true
    generation_watch_pid=""
  fi
  if [ -n "${generation_watch_file}" ] && [ -s "${generation_watch_file}" ]; then
    cp "${generation_watch_file}" \
      "${artifact_dir}/incomplete-generation-transition-watch.tsv"
  fi
  if [ -n "${generation_watch_error_file}" ] && [ -s "${generation_watch_error_file}" ]; then
    cp "${generation_watch_error_file}" \
      "${artifact_dir}/incomplete-generation-transition-watch.stderr"
  fi
  if [ -n "${generation_watch_raw_file}" ] && [ -s "${generation_watch_raw_file}" ]; then
    cp "${generation_watch_raw_file}" \
      "${artifact_dir}/incomplete-generation-transition-watch.jsonl"
  fi
  collect_artifacts
  chmod -R a+rX "${artifact_dir}" >/dev/null 2>&1
  if [ "${keep_namespace}" != "true" ]; then
    if [ "${namespace_created}" = "true" ]; then
      cleanup_test_namespace
    fi
    if [ "${PRODUCT_DATA_SERVICE_MODE:-bundled}" = "external" ]; then
      kube delete namespace "${namespace}-data" \
        --ignore-not-found --wait=false >/dev/null 2>&1
    fi
    if [ "${storage_mode}" = "static-nfs" ]; then
      kube delete pv \
        "conformance-knowledge-bases-${run_id}" \
        "conformance-manager-state-${run_id}" \
        "conformance-workspace-${run_id}" \
        "conformance-runtime-home-${run_id}" \
        --ignore-not-found --wait=false >/dev/null 2>&1
      kube delete storageclass "${storage_class}" \
        --ignore-not-found >/dev/null 2>&1
    fi
    kube delete pv \
      -l "aileron.io/product-conformance-run=${run_id}" \
      --ignore-not-found --wait=false >/dev/null 2>&1
    kube delete storageclass \
      -l "aileron.io/product-conformance-run=${run_id}" \
      --ignore-not-found >/dev/null 2>&1
    kube delete clusterrole,clusterrolebinding \
      -l "aileron.io/product-conformance-run=${run_id}" \
      --ignore-not-found --wait=false >/dev/null 2>&1
    kube delete clusterrole,clusterrolebinding \
      -l "aileron.io/test-run-id=${run_id}" \
      --ignore-not-found --wait=false >/dev/null 2>&1
    WORKSPACE_CRD_MANIFEST="${repo_root}/helm/aileron/crds/platform.aileron.io_workspaces.yaml" \
    WORKSPACE_CRD_ARTIFACT_DIR="${artifact_dir}" \
      "${repo_root}/scripts/test/kubernetes/crd-contract.sh" cleanup
  fi
  rm -rf "${render_dir}"
  exit "${exit_code}"
}

case "${run_id}" in
  ''|*[!a-z0-9-]*) fail "E2E_RUN_ID must contain only lowercase letters, digits, and hyphens" ;;
esac
case "${mode}" in
  local|diagnostic|platform) ;;
  *) fail "E2E_MODE must be local, diagnostic, or platform" ;;
esac
case "${runtime_home_access_mode}" in
  ReadWriteOnce|ReadWriteMany) ;;
  *) fail "RUNTIME_HOME_STORAGE_ACCESS_MODE must be ReadWriteOnce or ReadWriteMany" ;;
esac
case "${namespace}" in
  ''|*[!a-z0-9-]*) fail "E2E_NAMESPACE must be a lowercase DNS label" ;;
esac
[ "${#namespace}" -le 63 ] || fail "E2E_NAMESPACE must be at most 63 characters"
if [ -n "${image_pull_secret_source_namespace}" ] || \
  [ -n "${image_pull_secret_source_name}" ] || \
  [ -n "${image_pull_secret_name}" ]; then
  [ -n "${image_pull_secret_source_namespace}" ] || \
    fail "IMAGE_PULL_SECRET_SOURCE_NAMESPACE is required when a pull secret is configured"
  [ -n "${image_pull_secret_source_name}" ] || \
    fail "IMAGE_PULL_SECRET_SOURCE_NAME is required when a pull secret is configured"
  [ -n "${image_pull_secret_name}" ] || \
    fail "IMAGE_PULL_SECRET_NAME is required when a pull secret is configured"
  case "${image_pull_secret_name}" in
    *[!a-z0-9.-]*|.*|*.) fail "IMAGE_PULL_SECRET_NAME must be a DNS subdomain" ;;
  esac
fi

if [ -n "${workspace_contract_output_dir}" ]; then
  render_workspace_contract_fixtures "${workspace_contract_output_dir}"
  exit 0
fi

trap cleanup EXIT HUP INT TERM

mkdir -p "${artifact_dir}" "${render_dir}"
printf '%s\n' \
  'generation_label	runtime_instance_id	mount_revision	access_revision	component	pod_name	pod_uid	node' \
  > "${artifact_dir}/pod-generations.tsv"
printf 'pod_uid\tassertion\n' > "${artifact_dir}/pod-uid-absence.tsv"
printf 'pod_name\tassertion\n' > "${artifact_dir}/pod-name-absence.tsv"
printf 'transition\tevent_sequence\tevent_type\tpod_name\tpod_uid\tresource_version\tcomponent\truntime_instance_id\n' \
  > "${artifact_dir}/generation-transition-watch.tsv"
printf 'transition\traw_list_request\n' \
  > "${artifact_dir}/generation-list-request.tsv"
printf 'transition\tcollection_resource_version\tpod_name\tpod_uid\tpod_resource_version\tcomponent\truntime_instance_id\n' \
  > "${artifact_dir}/generation-list-snapshot.tsv"
printf 'transition\tstart_collection_resource_version\n' \
  > "${artifact_dir}/generation-watch-start-resource-version.tsv"
printf 'transition\traw_watch_request\n' \
  > "${artifact_dir}/generation-watch-request.tsv"
printf 'transition\texit_code\tstderr_bytes\n' \
  > "${artifact_dir}/generation-watch-process.tsv"
printf 'transition\tcomponent\tdesired_runtime_instance_id\tadded_event_resource_version\tadded_event_pod_uid\tfinal_pod_uid\tworkspace_status_pod_uid\n' \
  > "${artifact_dir}/generation-final-uid-binding.tsv"
prepare_kubeconfig
wait_until "two-node Kubernetes cluster" cluster_ready
select_nodes
create_namespace
copy_image_pull_secret
resolve_workload_probe_image
workspace_browser_image="$(
  resolve_product_workload_image "${BROWSER_IMAGE:?BROWSER_IMAGE is required}"
)"
resolve_storage_identity
setup_storage
create_runtime_secrets
install_operator
create_manager_writer
assert_wrong_storage_group_rejected
assert_root_squash
assert_locking
create_workspace
assert_runtime_scoped_secrets_isolated
spread_workloads
assert_runtime_home_contract
assert_same_generation_pod_recreate_refreshes_status
assert_runtime_home_persists_after_recreate
assert_deployments_stable
assert_isolated_pod_watch_pipeline
assert_workspace_rwx
record_generation baseline "${instance_1}" 0 0

baseline_uids="$(generation_uids)"
baseline_names="$(generation_names)"
start_generation_transition_watch attach
patch_workspace "${instance_2}" 1 0 \
  "[{\"kbId\":\"${kb_id}\",\"alias\":\"product\"}]"
wait_generation "${instance_2}" 1 0
finish_generation_transition_watch attach \
  "${baseline_uids}" "${baseline_names}" "${instance_2}"
generation_fencing_verified="true"
assert_runtime_mount product fixture-v1
record_generation attach "${instance_2}" 1 0

attached_uids="$(generation_uids)"
attached_names="$(generation_names)"
start_generation_transition_watch alias
patch_workspace "${instance_3}" 2 0 \
  "[{\"kbId\":\"${kb_id}\",\"alias\":\"runbook\"}]"
wait_generation "${instance_3}" 2 0
finish_generation_transition_watch alias \
  "${attached_uids}" "${attached_names}" "${instance_3}"
runtime_pod="$(pod_name workspace-runtime)"
kube exec -n "${namespace}" "${runtime_pod}" -- test ! -e /knowledge/product
assert_runtime_mount runbook fixture-v1
record_generation alias "${instance_3}" 2 0
assert_content_update_without_recreate

aliased_uids="$(generation_uids)"
aliased_names="$(generation_names)"
start_generation_transition_watch detach
patch_workspace "${instance_4}" 3 0 '[]'
wait_generation "${instance_4}" 3 0
finish_generation_transition_watch detach \
  "${aliased_uids}" "${aliased_names}" "${instance_4}"
runtime_pod="$(pod_name workspace-runtime)"
kube exec -n "${namespace}" "${runtime_pod}" -- test ! -e /knowledge/runbook
record_generation detach "${instance_4}" 3 0

detached_uids="$(generation_uids)"
detached_names="$(generation_names)"
start_generation_transition_watch reattach
patch_workspace "${instance_5}" 4 0 \
  "[{\"kbId\":\"${kb_id}\",\"alias\":\"runbook\"}]"
wait_generation "${instance_5}" 4 0
finish_generation_transition_watch reattach \
  "${detached_uids}" "${detached_names}" "${instance_5}"
assert_runtime_mount runbook fixture-v2
record_generation reattach "${instance_5}" 4 0

reattached_uids="$(generation_uids)"
reattached_names="$(generation_names)"
workspace_mount_contract_snapshot \
  > "${artifact_dir}/access-only-mount-contract-before.json"
start_generation_transition_watch access-recycle
patch_workspace_access_only "${instance_6}" 1
wait_generation "${instance_6}" 4 1
finish_generation_transition_watch access-recycle \
  "${reattached_uids}" "${reattached_names}" "${instance_6}"
workspace_mount_contract_snapshot \
  > "${artifact_dir}/access-only-mount-contract-after.json"
cmp -s \
  "${artifact_dir}/access-only-mount-contract-before.json" \
  "${artifact_dir}/access-only-mount-contract-after.json" || \
  fail "access-only mutation changed the Knowledge Base mount contract"
access_only_mount_contract_verified="true"
generation_watch_uid_binding_verified="true"
generation_watch_process_verified="true"
assert_runtime_mount runbook fixture-v2
record_generation access-recycle "${instance_6}" 4 1
assert_openshift_admission
delete_workspace_and_assert_absence
assert_product_hook

result="passed"
log "Operator storage, read-only mount, cross-node RWX, and generation fencing suite passed"
if [ "${product_lifecycle_verified}" != "true" ]; then
  log "Manager API lifecycle, durable jobs, action gate, signed drain, and browser pairing were not exercised"
fi

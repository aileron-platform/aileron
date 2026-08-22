#!/bin/sh

set -eu

repo_root="${REPO_ROOT:-/repo}"
namespace="${E2E_NAMESPACE:?E2E_NAMESPACE is required}"
run_id="${E2E_RUN_ID:?E2E_RUN_ID is required}"
release="${PRODUCT_HELM_RELEASE:-product}"
driver_image="${PRODUCT_DRIVER_IMAGE:?PRODUCT_DRIVER_IMAGE is required}"
manager_image="${MANAGER_IMAGE:?MANAGER_IMAGE is required}"
runtime_image="${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}"
browser_image="${BROWSER_IMAGE:?BROWSER_IMAGE is required}"
canvas_image="${CANVAS_IMAGE:?CANVAS_IMAGE is required}"
redis_image="${REDIS_IMAGE:?REDIS_IMAGE is required}"
postgres_image="${POSTGRES_IMAGE:?POSTGRES_IMAGE is required}"
storage_mode="${E2E_STORAGE_MODE:?E2E_STORAGE_MODE is required}"
storage_class="${RWX_STORAGE_CLASS:?RWX_STORAGE_CLASS is required}"
rwo_storage_class="${RWO_STORAGE_CLASS:?RWO_STORAGE_CLASS is required}"
image_pull_policy="${IMAGE_PULL_POLICY:-Never}"
image_pull_secret_name="${IMAGE_PULL_SECRET_NAME:-}"
storage_gid="${PLATFORM_STORAGE_GID:-2000}"
shared_storage_size="${E2E_SHARED_STORAGE_SIZE:-1Gi}"
rwo_storage_size="${E2E_RWO_STORAGE_SIZE:-1Gi}"
runtime_home_storage_size="${E2E_RUNTIME_HOME_STORAGE_SIZE:-2Gi}"
service_account="product-conformance"
resource_suffix="$(printf '%s' "${run_id}" | tr -c 'a-zA-Z0-9-' '-')"
fullname="${release}-aileron"
work_dir="$(mktemp -d)"
runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-${rwo_storage_class}}"
runtime_home_storage_access_mode="${RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"
data_service_mode="${PRODUCT_DATA_SERVICE_MODE:-bundled}"
data_service_namespace="${PRODUCT_DATA_SERVICE_NAMESPACE:-${namespace}-data}"

trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM

log() {
  printf '[product-stack] %s\n' "$*"
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
  k3s kubectl "$@"
}

wait_for_job_complete() {
  job_name="$1"
  timeout_seconds="$2"
  attempts="${timeout_seconds}"
  while [ "${attempts}" -gt 0 ]; do
    job_complete="$(kube get job "${job_name}" -n "${namespace}" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || true)"
    [ "${job_complete}" = "True" ] && return 0
    job_failed="$(kube get job "${job_name}" -n "${namespace}" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)"
    if [ "${job_failed}" = "True" ]; then
      kube logs "job/${job_name}" -n "${namespace}" --all-containers=true >&2 || true
      kube describe job "${job_name}" -n "${namespace}" >&2 || true
      fail "Job ${job_name} failed"
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  kube get pods -n "${namespace}" -l "job-name=${job_name}" -o wide >&2 || true
  kube describe job "${job_name}" -n "${namespace}" >&2 || true
  kube logs "job/${job_name}" -n "${namespace}" --all-containers=true >&2 || true
  fail "timed out waiting for Job ${job_name}"
}

case "${runtime_home_storage_access_mode}" in
  ReadWriteOnce|ReadWriteMany) ;;
  *)
    fail "RUNTIME_HOME_STORAGE_ACCESS_MODE must be ReadWriteOnce or ReadWriteMany"
    ;;
esac

case "${data_service_mode}" in
  bundled|external) ;;
  *) fail "PRODUCT_DATA_SERVICE_MODE must be bundled or external" ;;
esac
case "${data_service_namespace}" in
  ''|*[!a-z0-9-]*) fail "PRODUCT_DATA_SERVICE_NAMESPACE must be a lowercase DNS label" ;;
esac
[ "${#data_service_namespace}" -le 63 ] || \
  fail "PRODUCT_DATA_SERVICE_NAMESPACE must be at most 63 characters"

case "${storage_mode}" in
  static-nfs)
    nfs_server="${NFS_SERVER:?NFS_SERVER is required for static-nfs storage}"
    [ "${rwo_storage_class}" = "${storage_class}" ] || \
      fail "static-nfs requires RWO_STORAGE_CLASS to match RWX_STORAGE_CLASS"
    [ "${runtime_home_storage_class}" = "${storage_class}" ] || \
      fail "static-nfs requires RUNTIME_HOME_STORAGE_CLASS to match RWX_STORAGE_CLASS"
    ;;
  dynamic)
    nfs_server=""
    ;;
  *)
    fail "E2E_STORAGE_MODE must be static-nfs or dynamic"
    ;;
esac

image_pull_secrets_block=""
pod_image_pull_secrets_block=""
job_image_pull_secrets_block=""
if [ -n "${image_pull_secret_name}" ]; then
  case "${image_pull_secret_name}" in
    *[!a-z0-9.-]*|.*|*.) fail "IMAGE_PULL_SECRET_NAME must be a DNS subdomain" ;;
  esac
  image_pull_secrets_block="imagePullSecrets:
  - name: ${image_pull_secret_name}"
  pod_image_pull_secrets_block="  imagePullSecrets:
    - name: ${image_pull_secret_name}"
  job_image_pull_secrets_block="      imagePullSecrets:
        - name: ${image_pull_secret_name}"
fi

split_image() {
  image="$1"
  image_digest=""
  case "${image}" in
    *@sha256:*)
      image_repository="${image%@sha256:*}"
      image_digest="sha256:${image##*@sha256:}"
      image_tag=""
      printf '%s\n' "${image_digest}" | \
        grep -Eq '^sha256:[0-9a-f]{64}$' || \
        fail "image digest must be sha256: ${image}"
      ;;
    *)
      image_name="${image##*/}"
      case "${image_name}" in
        *:*)
          image_repository="${image%:*}"
          image_tag="${image##*:}"
          ;;
        *)
          fail "image must include a tag or sha256 digest: ${image}"
          ;;
      esac
      ;;
  esac
  [ -n "${image_repository}" ] || fail "image repository is empty: ${image}"
  if [ -z "${image_digest}" ] && [ -z "${image_tag}" ]; then
    fail "image tag is empty: ${image}"
  fi
}

command -v helm >/dev/null 2>&1 || fail "helm is required"
split_image "${manager_image}"
manager_repository="${image_repository}"
manager_tag="${image_tag}"
manager_digest="${image_digest}"
split_image "${runtime_image}"
runtime_repository="${image_repository}"
runtime_tag="${image_tag}"
runtime_digest="${image_digest}"
[ -n "${runtime_digest}" ] || \
  fail "RUNTIME_IMAGE must be an immutable sha256 reference"
split_image "${browser_image}"
browser_repository="${image_repository}"
browser_tag="${image_tag}"
browser_digest="${image_digest}"
[ -n "${browser_digest}" ] || \
  fail "BROWSER_IMAGE must be an immutable sha256 reference"
split_image "${canvas_image}"
canvas_repository="${image_repository}"
canvas_tag="${image_tag}"
canvas_digest="${image_digest}"
[ -n "${canvas_digest}" ] || \
  fail "CANVAS_IMAGE must be an immutable sha256 reference"
split_image "${redis_image}"
redis_repository="${image_repository}"
redis_tag="${image_tag}"
redis_digest="${image_digest}"
split_image "${postgres_image}"
postgres_repository="${image_repository}"
postgres_tag="${image_tag}"
postgres_digest="${image_digest}"

kube get namespace "${namespace}" >/dev/null
kube get storageclass "${storage_class}" >/dev/null
kube get storageclass "${rwo_storage_class}" >/dev/null
kube get storageclass "${runtime_home_storage_class}" >/dev/null
if [ "${storage_mode}" = "static-nfs" ]; then
  runtime_home_provisioner="$(kube get storageclass \
    "${runtime_home_storage_class}" -o jsonpath='{.provisioner}')"
  [ "${runtime_home_provisioner}" = "kubernetes.io/no-provisioner" ] || \
    fail "static-nfs Runtime HOME StorageClass must use kubernetes.io/no-provisioner"
  runtime_home_binding_mode="$(kube get storageclass \
    "${runtime_home_storage_class}" -o jsonpath='{.volumeBindingMode}')"
  [ "${runtime_home_binding_mode}" = "Immediate" ] || \
    fail "static-nfs Runtime HOME StorageClass must use Immediate binding"
  runtime_home_reclaim_policy="$(kube get storageclass \
    "${runtime_home_storage_class}" -o jsonpath='{.reclaimPolicy}')"
  [ "${runtime_home_reclaim_policy}" = "Retain" ] || \
    fail "static-nfs Runtime HOME StorageClass must use Retain reclaim policy"
  source_pvc_phase="$(kube get pvc knowledge-bases-pvc -n "${namespace}" \
    -o jsonpath='{.status.phase}')"
  [ "${source_pvc_phase}" = "Bound" ] || \
    fail "knowledge-bases-pvc is not Bound"
  source_pv="$(kube get pvc knowledge-bases-pvc -n "${namespace}" \
    -o jsonpath='{.spec.volumeName}')"
  [ -n "${source_pv}" ] || fail "knowledge-bases-pvc has no bound PV"
  source_nfs_server="$(kube get pv "${source_pv}" \
    -o jsonpath='{.spec.nfs.server}')"
  [ -n "${source_nfs_server}" ] || fail "source PV is not NFS"
  [ "${source_nfs_server}" = "${nfs_server}" ] || \
    fail "source PV NFS server does not match NFS_SERVER"
  static_nfs_mount_options="$(kube get pv "${source_pv}" \
    -o jsonpath='{range .spec.mountOptions[*]}{@}{"\n"}{end}')"
  [ -n "${static_nfs_mount_options}" ] || \
    fail "source PV has no NFS mountOptions"
  if printf '%s\n' "${static_nfs_mount_options}" | \
    grep -Eqv '^[A-Za-z0-9._=,+:/-]+$'; then
    fail "source PV contains an unsafe NFS mountOption"
  fi
  static_nfs_mount_options_yaml="$(printf '%s\n' "${static_nfs_mount_options}" | \
    awk 'NF {printf "    - \"%s\"\n", $0}')"
fi

cat > "${work_dir}/harness-rbac.yaml" <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${service_account}
  namespace: ${namespace}
${image_pull_secrets_block}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ${service_account}
  namespace: ${namespace}
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "persistentvolumeclaims", "secrets", "configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: [""]
    resources: ["serviceaccounts"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["get", "create"]
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["list"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "watch", "update", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments/scale"]
    verbs: ["get", "update", "patch"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: ["platform.aileron.io"]
    resources: ["workspaces"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${service_account}
  namespace: ${namespace}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: ${service_account}
subjects:
  - kind: ServiceAccount
    name: ${service_account}
    namespace: ${namespace}
EOF

persistent_volume_rule=""
if [ "${storage_mode}" = "static-nfs" ]; then
  persistent_volume_rule='  - apiGroups: [""]
    resources: ["persistentvolumes"]
    verbs: ["get", "list", "watch", "create", "patch", "delete"]'
fi
cat >> "${work_dir}/harness-rbac.yaml" <<EOF
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: product-conformance-pv-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
rules:
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get"]
${persistent_volume_rule}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: product-conformance-pv-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: product-conformance-pv-${resource_suffix}
subjects:
  - kind: ServiceAccount
    name: ${service_account}
    namespace: ${namespace}
EOF
kube apply -f "${work_dir}/harness-rbac.yaml" >/dev/null

prepare_platform_secret() {
  database_host="${fullname}-postgres"
  database_username="postgres"
  database_password="product-postgres-password"
  database_query=""
  redis_scheme="redis"
  redis_host="${fullname}-redis"
  redis_password=""

  if [ "${data_service_mode}" = "external" ]; then
    command -v openssl >/dev/null 2>&1 || fail "openssl is required for external data-service TLS"
    database_host="external-postgres.${data_service_namespace}.svc.cluster.local"
    database_username="platform_login"
    database_password="platform_password"
    database_query="?sslmode=verify-full&sslrootcert=/etc/aileron/data-service-ca/platform-database/ca.crt"
    redis_scheme="rediss"
    redis_host="external-redis.${data_service_namespace}.svc.cluster.local"
    redis_password="external_redis_password"

    tls_dir="${work_dir}/data-service-tls"
    mkdir -p "${tls_dir}"
    chmod 0700 "${tls_dir}"
    if ! openssl req -config /dev/null -x509 -newkey rsa:2048 -nodes -days 1 \
      -subj '/CN=Aileron disposable data-service CA' \
      -addext 'basicConstraints=critical,CA:TRUE' \
      -addext 'keyUsage=critical,keyCertSign,cRLSign' \
      -keyout "${tls_dir}/ca.key" -out "${tls_dir}/ca.crt" \
      2> "${tls_dir}/ca-error.log"; then
      cat "${tls_dir}/ca-error.log" >&2
      fail "failed to generate the disposable data-service CA"
    fi
    for service in postgres redis; do
      service_host="external-${service}.${data_service_namespace}.svc.cluster.local"
      if ! openssl req -config /dev/null -newkey rsa:2048 -nodes \
        -subj "/CN=external-${service}" \
        -keyout "${tls_dir}/${service}.key" \
        -out "${tls_dir}/${service}.csr" \
        2> "${tls_dir}/${service}-csr-error.log"; then
        cat "${tls_dir}/${service}-csr-error.log" >&2
        fail "failed to generate the disposable ${service} CSR"
      fi
      printf 'subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n' "${service_host}" \
        > "${tls_dir}/${service}.ext"
      if ! openssl x509 -req -days 1 -sha256 \
        -in "${tls_dir}/${service}.csr" \
        -CA "${tls_dir}/ca.crt" -CAkey "${tls_dir}/ca.key" -CAcreateserial \
        -extfile "${tls_dir}/${service}.ext" \
        -out "${tls_dir}/${service}.crt" \
        2> "${tls_dir}/${service}-sign-error.log"; then
        cat "${tls_dir}/${service}-sign-error.log" >&2
        fail "failed to sign the disposable ${service} certificate"
      fi
    done
    chmod 0600 "${tls_dir}"/*.key

    ca_data="$(base64 < "${tls_dir}/ca.crt" | tr -d '\n')"
    postgres_cert_data="$(base64 < "${tls_dir}/postgres.crt" | tr -d '\n')"
    postgres_key_data="$(base64 < "${tls_dir}/postgres.key" | tr -d '\n')"
    redis_cert_data="$(base64 < "${tls_dir}/redis.crt" | tr -d '\n')"
    redis_key_data="$(base64 < "${tls_dir}/redis.key" | tr -d '\n')"
    cat > "${work_dir}/external-data-services.yaml" <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${data_service_namespace}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
---
apiVersion: v1
kind: Secret
metadata:
  name: external-postgres-tls
  namespace: ${data_service_namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
  tls.crt: ${postgres_cert_data}
  tls.key: ${postgres_key_data}
---
apiVersion: v1
kind: Secret
metadata:
  name: external-redis-tls
  namespace: ${data_service_namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
  tls.crt: ${redis_cert_data}
  tls.key: ${redis_key_data}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: external-postgres-init
  namespace: ${data_service_namespace}
data:
  001-platform-login.sql: |
    CREATE ROLE platform_login WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE INHERIT NOREPLICATION NOBYPASSRLS PASSWORD 'platform_password';
    ALTER DATABASE aileron OWNER TO platform_login;
    GRANT pg_signal_backend TO platform_login;
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: external-postgres-data
  namespace: ${data_service_namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: external-postgres
  namespace: ${data_service_namespace}
spec:
  selector:
    app.kubernetes.io/name: external-postgres
  ports:
    - name: postgres
      port: 5432
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-postgres
  namespace: ${data_service_namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: external-postgres
  template:
    metadata:
      labels:
        app.kubernetes.io/name: external-postgres
    spec:
      securityContext:
        fsGroup: 70
        fsGroupChangePolicy: OnRootMismatch
        runAsGroup: 70
        runAsNonRoot: true
        runAsUser: 70
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: postgres
          image: ${postgres_image}
          imagePullPolicy: ${image_pull_policy}
          args:
            - -c
            - ssl=on
            - -c
            - ssl_cert_file=/etc/postgres-tls/tls.crt
            - -c
            - ssl_key_file=/etc/postgres-tls/tls.key
            - -c
            - ssl_ca_file=/etc/postgres-tls/ca.crt
          env:
            - name: POSTGRES_DB
              value: aileron
            - name: POSTGRES_USER
              value: bootstrap_superuser
            - name: POSTGRES_PASSWORD
              value: bootstrap_password
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "bootstrap_superuser", "-d", "aileron"]
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: init
              mountPath: /docker-entrypoint-initdb.d
              readOnly: true
            - name: tls
              mountPath: /etc/postgres-tls
              readOnly: true
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: external-postgres-data
        - name: init
          configMap:
            name: external-postgres-init
        - name: tls
          secret:
            secretName: external-postgres-tls
            defaultMode: 0440
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: external-redis-data
  namespace: ${data_service_namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: external-redis
  namespace: ${data_service_namespace}
spec:
  selector:
    app.kubernetes.io/name: external-redis
  ports:
    - name: rediss
      port: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-redis
  namespace: ${data_service_namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: external-redis
  template:
    metadata:
      labels:
        app.kubernetes.io/name: external-redis
    spec:
      securityContext:
        fsGroup: 65532
        fsGroupChangePolicy: OnRootMismatch
        runAsGroup: 65532
        runAsNonRoot: true
        runAsUser: 65532
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: redis
          image: ${redis_image}
          imagePullPolicy: ${image_pull_policy}
          args:
            - --port
            - "0"
            - --tls-port
            - "6379"
            - --tls-cert-file
            - /etc/redis-tls/tls.crt
            - --tls-key-file
            - /etc/redis-tls/tls.key
            - --tls-ca-cert-file
            - /etc/redis-tls/ca.crt
            - --tls-auth-clients
            - "no"
            - --requirepass
            - external_redis_password
            - --appendonly
            - "yes"
            - --maxmemory-policy
            - noeviction
          readinessProbe:
            exec:
              command: ["redis-cli", "--tls", "--cacert", "/etc/redis-tls/ca.crt", "--sni", "${redis_host}", "-h", "127.0.0.1", "-a", "external_redis_password", "ping"]
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: data
              mountPath: /data
            - name: tls
              mountPath: /etc/redis-tls
              readOnly: true
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: external-redis-data
        - name: tls
          secret:
            secretName: external-redis-tls
            defaultMode: 0440
EOF
    kube apply -f "${work_dir}/external-data-services.yaml" >/dev/null
    kube rollout status deployment/external-postgres \
      -n "${data_service_namespace}" --timeout=300s >/dev/null
    kube rollout status deployment/external-redis \
      -n "${data_service_namespace}" --timeout=300s >/dev/null
  fi

  redis_auth=""
  if [ -n "${redis_password}" ]; then
    redis_auth=":${redis_password}@"
  fi
  cat > "${work_dir}/platform-data-service-secrets.yaml" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: aileron-platform-secrets
  namespace: ${namespace}
type: Opaque
stringData:
  database-url: postgresql://${database_username}:${database_password}@${database_host}:5432/aileron${database_query}
  runtime-database-credential-key: product-runtime-database-credential-key-v1
  postgres-username: ${database_username}
  postgres-password: ${database_password}
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-general
  namespace: ${namespace}
type: Opaque
stringData:
  url: ${redis_scheme}://${redis_auth}${redis_host}:6379/0
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-job-queue
  namespace: ${namespace}
type: Opaque
stringData:
  url: ${redis_scheme}://${redis_auth}${redis_host}:6379/1
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-job-result
  namespace: ${namespace}
type: Opaque
stringData:
  url: ${redis_scheme}://${redis_auth}${redis_host}:6379/2
EOF
  if [ "${data_service_mode}" = "external" ]; then
    cat >> "${work_dir}/platform-data-service-secrets.yaml" <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: product-platform-database-ca
  namespace: ${namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-general-ca
  namespace: ${namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-job-queue-ca
  namespace: ${namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
---
apiVersion: v1
kind: Secret
metadata:
  name: product-redis-job-result-ca
  namespace: ${namespace}
type: Opaque
data:
  ca.crt: ${ca_data}
EOF
  fi
  kube apply -f "${work_dir}/platform-data-service-secrets.yaml" >/dev/null
}

if [ "${storage_mode}" = "static-nfs" ]; then
  cat > "${work_dir}/storage-preparer.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: product-storage-preparer
  namespace: ${namespace}
spec:
${pod_image_pull_secrets_block}
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000860099
    runAsGroup: 1000860099
    fsGroup: ${storage_gid}
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: prepare
      image: ${driver_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args:
        - >-
          umask 0007;
          mkdir -p /manager-state/product/${run_id}/postgres /manager-state/product/${run_id}/redis /manager-state/product/${run_id}/identity-backup;
          chgrp ${storage_gid} /manager-state/product/${run_id}/postgres /manager-state/product/${run_id}/redis /manager-state/product/${run_id}/identity-backup;
          chmod 2770 /manager-state/product/${run_id}/postgres /manager-state/product/${run_id}/redis;
          chmod 2770 /manager-state/product/${run_id}/identity-backup
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
      volumeMounts:
        - name: manager-state
          mountPath: /manager-state
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: manager-state
      persistentVolumeClaim:
        claimName: manager-state-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube delete pod product-storage-preparer -n "${namespace}" --ignore-not-found --wait=true >/dev/null
  kube apply -f "${work_dir}/storage-preparer.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Succeeded \
    pod/product-storage-preparer -n "${namespace}" --timeout=180s >/dev/null
  kube delete pod product-storage-preparer -n "${namespace}" --wait=true >/dev/null

  cat > "${work_dir}/product-storage.yaml" <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-kb-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${shared_storage_size}}
  accessModes: [ReadWriteMany]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: product-knowledge-bases-pvc
  nfs:
    server: ${nfs_server}
    path: /knowledge-bases
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-manager-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${rwo_storage_size}}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: product-manager-state-pvc
  nfs:
    server: ${nfs_server}
    path: /manager-state
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-postgres-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${rwo_storage_size}}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: data-${fullname}-postgres-0
  nfs:
    server: ${nfs_server}
    path: /manager-state/product/${run_id}/postgres
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-redis-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${rwo_storage_size}}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: data-${fullname}-redis-0
  nfs:
    server: ${nfs_server}
    path: /manager-state/product/${run_id}/redis
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-workspaces-root-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${shared_storage_size}}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: product-workspaces-root-pvc
  nfs:
    server: ${nfs_server}
    path: /workspaces
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: product-workspaces-root-pvc
  namespace: ${namespace}
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: ${shared_storage_size}
  storageClassName: ${storage_class}
  volumeName: product-workspaces-root-${resource_suffix}
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-runtime-homes-root-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${runtime_home_storage_size}}
  accessModes: [ReadWriteMany]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  claimRef:
    namespace: ${namespace}
    name: product-runtime-homes-root-pvc
  nfs:
    server: ${nfs_server}
    path: /runtime-homes
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: product-runtime-homes-root-pvc
  namespace: ${namespace}
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: ${runtime_home_storage_size}
  storageClassName: ${storage_class}
  volumeName: product-runtime-homes-root-${resource_suffix}
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: product-runtime-home-${resource_suffix}
  labels:
    aileron.io/product-conformance-run: ${resource_suffix}
spec:
  capacity: {storage: ${runtime_home_storage_size}}
  accessModes: [${runtime_home_storage_access_mode}]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${runtime_home_storage_class}
  mountOptions:
${static_nfs_mount_options_yaml}
  nfs:
    server: ${nfs_server}
    path: /runtime-homes/product-${run_id}
EOF
  kube apply -f "${work_dir}/product-storage.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Bound \
    pvc/product-runtime-homes-root-pvc \
    -n "${namespace}" --timeout=180s >/dev/null

  cat > "${work_dir}/runtime-home-preparer.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: product-runtime-home-preparer
  namespace: ${namespace}
spec:
${pod_image_pull_secrets_block}
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000860099
    runAsGroup: 1000860099
    fsGroup: ${storage_gid}
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: prepare
      image: ${driver_image}
      imagePullPolicy: ${image_pull_policy}
      command: ["/bin/sh", "-ec"]
      args:
        - >-
          umask 0007;
          mkdir -p /runtime-homes/product-${run_id};
          chmod 2770 /runtime-homes/product-${run_id}
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
      volumeMounts:
        - name: runtime-homes
          mountPath: /runtime-homes
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: runtime-homes
      persistentVolumeClaim:
        claimName: product-runtime-homes-root-pvc
    - name: tmp
      emptyDir: {}
EOF
  kube delete pod product-runtime-home-preparer -n "${namespace}" \
    --ignore-not-found --wait=true >/dev/null
  kube apply -f "${work_dir}/runtime-home-preparer.yaml" >/dev/null
  kube wait --for=jsonpath='{.status.phase}'=Succeeded \
    pod/product-runtime-home-preparer -n "${namespace}" \
    --timeout=180s >/dev/null
  kube delete pod product-runtime-home-preparer -n "${namespace}" \
    --wait=true >/dev/null
fi

cat > "${work_dir}/keygen-job.yaml" <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: product-assertion-keygen
  namespace: ${namespace}
spec:
  backoffLimit: 0
  template:
    spec:
${job_image_pull_secrets_block}
      restartPolicy: Never
      serviceAccountName: ${service_account}
      containers:
        - name: keygen
          image: ${driver_image}
          imagePullPolicy: ${image_pull_policy}
          args: ["prepare-keys"]
          env:
            - name: E2E_NAMESPACE
              value: ${namespace}
            - name: PRODUCT_ASSERTION_KEY_ID
              value: product-conformance-${resource_suffix}
        - name: oidc-tls
          image: ${driver_image}
          imagePullPolicy: ${image_pull_policy}
          args: ["prepare-oidc-fixture-tls"]
          env:
            - name: E2E_NAMESPACE
              value: ${namespace}
            - name: OIDC_FIXTURE_HOSTNAME
              value: ${fullname}-oidc-fixture
EOF
kube delete job product-assertion-keygen -n "${namespace}" --ignore-not-found --wait=true >/dev/null
kube apply -f "${work_dir}/keygen-job.yaml" >/dev/null
wait_for_job_complete product-assertion-keygen 180

oidc_client_secret_file="${work_dir}/external-oidc-client-secret"
(
  umask 077
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n' > "${oidc_client_secret_file}"
)
[ "$(wc -c < "${oidc_client_secret_file}" | tr -d ' ')" -eq 64 ] || \
  fail "failed to generate the external OIDC client secret"
chmod 0600 "${oidc_client_secret_file}"
kube delete secret external-oidc-client -n "${namespace}" \
  --ignore-not-found --wait=true >/dev/null
kube create secret generic external-oidc-client -n "${namespace}" \
  --from-file="client-secret=${oidc_client_secret_file}" >/dev/null

cat > "${work_dir}/external-oidc-fixture.yaml" <<EOF
apiVersion: v1
kind: Service
metadata:
  name: ${fullname}-oidc-fixture
  namespace: ${namespace}
spec:
  selector:
    app.kubernetes.io/name: ${fullname}-oidc-fixture
  ports:
    - name: https
      port: 8443
      targetPort: https
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${fullname}-oidc-fixture
  namespace: ${namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${fullname}-oidc-fixture
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${fullname}-oidc-fixture
    spec:
${pod_image_pull_secrets_block}
      automountServiceAccountToken: false
      containers:
        - name: oidc-fixture
          image: ${driver_image}
          imagePullPolicy: ${image_pull_policy}
          args: ["serve-oidc-fixture"]
          env:
            - name: OIDC_FIXTURE_ISSUER
              value: https://${fullname}-oidc-fixture:8443
            - name: OIDC_FIXTURE_CLIENT_ID
              value: aileron-manager
            - name: OIDC_FIXTURE_CLIENT_SECRET_FILE
              value: /etc/aileron/oidc-client/client-secret
            - name: OIDC_FIXTURE_TLS_CERT_FILE
              value: /etc/aileron/oidc-tls/tls.crt
            - name: OIDC_FIXTURE_TLS_KEY_FILE
              value: /etc/aileron/oidc-tls/tls.key
          ports:
            - name: https
              containerPort: 8443
          readinessProbe:
            httpGet:
              path: /.well-known/openid-configuration
              port: https
              scheme: HTTPS
          volumeMounts:
            - name: oidc-client
              mountPath: /etc/aileron/oidc-client
              readOnly: true
            - name: oidc-tls
              mountPath: /etc/aileron/oidc-tls
              readOnly: true
      volumes:
        - name: oidc-client
          secret:
            secretName: external-oidc-client
            defaultMode: 0400
            items:
              - key: client-secret
                path: client-secret
        - name: oidc-tls
          secret:
            secretName: external-oidc-tls
EOF
kube apply -f "${work_dir}/external-oidc-fixture.yaml" >/dev/null
kube rollout status "deployment/${fullname}-oidc-fixture" -n "${namespace}" --timeout=180s >/dev/null

if [ "${PRODUCT_STACK_TRACE:-false}" = "true" ]; then
  set -x
fi
prepare_platform_secret
if [ "${PRODUCT_STACK_TRACE:-false}" = "true" ]; then
  set +x
fi

set -- upgrade --install "${release}" "${repo_root}/helm/aileron" \
  --namespace "${namespace}" \
  --values "${repo_root}/helm/aileron/tests/values/product-conformance.yaml" \
  --set-string platformPublicOrigin=https://aileron.example.test \
  --set-string kubernetes.workspaceRuntimeNamespace="${namespace}" \
  --set-string kubernetes.workspaceData.size="${shared_storage_size}" \
  --set-string kubernetes.workspaceData.storageClassName="${storage_class}" \
  --set-string kubernetes.runtimeHome.size="${runtime_home_storage_size}" \
  --set-string kubernetes.runtimeHome.storageClassName="${runtime_home_storage_class}" \
  --set-string kubernetes.runtimeHome.accessMode="${runtime_home_storage_access_mode}" \
  --set-string kubernetes.knowledgeBases.size="${shared_storage_size}" \
  --set-string kubernetes.knowledgeBases.storageClassName="${storage_class}" \
  --set-string kubernetes.managerState.size="${rwo_storage_size}" \
  --set-string kubernetes.managerState.storageClassName="${rwo_storage_class}" \
  --set kubernetes.platformStorageGid="${storage_gid}" \
  --set-string workspaceManager.image.repository="${manager_repository}" \
  --set-string workspaceManager.image.digest="${manager_digest}" \
  --set-string workspaceManager.image.tag="${manager_tag}" \
  --set-string workspaceManager.image.pullPolicy="${image_pull_policy}" \
  --set-string workspaceOperator.runtimeImage.repository="${runtime_repository}" \
  --set-string workspaceOperator.runtimeImage.digest="${runtime_digest}" \
  --set-string workspaceOperator.runtimeImage.tag="${runtime_tag}" \
  --set-string kubernetes.browserImage.repository="${browser_repository}" \
  --set-string kubernetes.browserImage.digest="${browser_digest}" \
  --set-string kubernetes.browserImage.tag="${browser_tag}" \
  --set-string kubernetes.canvasImage.repository="${canvas_repository}" \
  --set-string kubernetes.canvasImage.digest="${canvas_digest}" \
  --set-string kubernetes.canvasImage.tag="${canvas_tag}" \
  --set-string redis.image.repository="${redis_repository}" \
  --set-string redis.image.digest="${redis_digest}" \
  --set-string redis.image.tag="${redis_tag}" \
  --set-string redis.image.pullPolicy="${image_pull_policy}" \
  --set-string redis.persistence.size="${rwo_storage_size}" \
  --set-string redis.persistence.storageClassName="${rwo_storage_class}" \
  --set-string postgres.image.repository="${postgres_repository}" \
  --set-string postgres.image.digest="${postgres_digest}" \
  --set-string postgres.image.tag="${postgres_tag}" \
  --set-string postgres.image.pullPolicy="${image_pull_policy}" \
  --set-string postgres.persistence.size="${rwo_storage_size}" \
  --set-string postgres.persistence.storageClassName="${rwo_storage_class}" \
  --set-string oidc.issuerUrl="https://${fullname}-oidc-fixture:8443" \
  --set-string oidc.clientId="aileron-manager" \
  --set-string oidc.clientSecretName="external-oidc-client" \
  --set-string oidc.caSecretName="external-oidc-tls" \
  --set-string runtimeAssertions.activeKid="product-conformance-${resource_suffix}"
if [ "${data_service_mode}" = "external" ]; then
  set -- "$@" \
    --set postgres.enabled=false \
    --set-string platformDatabase.revision=product-platform-database-v1 \
    --set-string platformDatabase.caSecretName=product-platform-database-ca \
    --set-string platformDatabase.caSecretKey=ca.crt \
    --set redis.enabled=false \
    --set-string redis.connections.general.revision=product-redis-general-v1 \
    --set-string redis.connections.general.urlSecretName=product-redis-general \
    --set-string redis.connections.general.urlSecretKey=url \
    --set-string redis.connections.general.caSecretName=product-redis-general-ca \
    --set-string redis.connections.general.caSecretKey=ca.crt \
    --set-string redis.connections.jobQueue.revision=product-redis-job-queue-v1 \
    --set-string redis.connections.jobQueue.urlSecretName=product-redis-job-queue \
    --set-string redis.connections.jobQueue.urlSecretKey=url \
    --set-string redis.connections.jobQueue.caSecretName=product-redis-job-queue-ca \
    --set-string redis.connections.jobQueue.caSecretKey=ca.crt \
    --set-string redis.connections.jobResult.revision=product-redis-job-result-v1 \
    --set-string redis.connections.jobResult.urlSecretName=product-redis-job-result \
    --set-string redis.connections.jobResult.urlSecretKey=url \
    --set-string redis.connections.jobResult.caSecretName=product-redis-job-result-ca \
    --set-string redis.connections.jobResult.caSecretKey=ca.crt
fi
if [ -n "${image_pull_secret_name}" ]; then
  set -- "$@" \
    --set-string "global.imagePullSecrets[0].name=${image_pull_secret_name}"
fi
set -- "$@" \
  --wait \
  --timeout 10m
if ! helm "$@"; then
  kube logs "job/${fullname}-data-service-preflight" -n "${namespace}" \
    --all-containers=true >&2 || true
  kube describe job "${fullname}-data-service-preflight" \
    -n "${namespace}" >&2 || true
  fail "Helm install or upgrade failed"
fi

if [ "${data_service_mode}" = "bundled" ]; then
  kube rollout status "statefulset/${fullname}-postgres" -n "${namespace}" --timeout=300s >/dev/null
  kube rollout status "statefulset/${fullname}-redis" -n "${namespace}" --timeout=300s >/dev/null
else
  [ -z "$(kube get statefulset "${fullname}-postgres" -n "${namespace}" \
    --ignore-not-found -o name)" ] || fail "external mode rendered bundled PostgreSQL"
  [ -z "$(kube get statefulset "${fullname}-redis" -n "${namespace}" \
    --ignore-not-found -o name)" ] || fail "external mode rendered bundled Redis"
fi
kube rollout status "deployment/${fullname}-workspace-manager" -n "${namespace}" --timeout=300s >/dev/null

# The pre-existing E2E Operator remains the sole controller. Point newly
# reconciled Runtime Pods at this formal Manager.
kube set env deployment/workspace-operator -n "${namespace}" \
  "AILERON_MANAGER_INTERNAL_URL=http://${fullname}-workspace-manager:3001" \
  "KNOWLEDGE_BASES_PVC_NAME=product-knowledge-bases-pvc" \
  "RUNTIME_HOME_STORAGE_CLASS_NAME=${runtime_home_storage_class}" \
  "RUNTIME_HOME_STORAGE_SIZE=${runtime_home_storage_size}" \
  "RUNTIME_HOME_STORAGE_ACCESS_MODE=${runtime_home_storage_access_mode}" >/dev/null
kube rollout status deployment/workspace-operator \
  -n "${namespace}" --timeout=300s >/dev/null

manager_pod="$(kube get pod -n "${namespace}" \
  -l app.kubernetes.io/component=workspace-manager \
  -o jsonpath='{.items[0].metadata.name}')"
kube exec -n "${namespace}" "${manager_pod}" -- \
  supervisorctl -c /workspace-manager/supervisord.kubernetes.conf status \
  | tee "${work_dir}/supervisor-status.txt"
for process in fastapi celery-worker celery-beat; do
  grep -Eq "^${process}[[:space:]]+RUNNING" "${work_dir}/supervisor-status.txt" || \
    fail "Manager process is not running: ${process}"
done

log "formal product stack is ready"

#!/bin/sh

set -eu

KUBECTL="${KUBECTL:-kubectl}"
context=""
NFS_DELETE_CLASS="${NFS_DELETE_CLASS:-aileron-nfs-rwx-delete}"
NFS_RETAIN_CLASS="${NFS_RETAIN_CLASS:-aileron-nfs-rwx-retain}"
LOCAL_DELETE_CLASS="${LOCAL_DELETE_CLASS:-aileron-local-rwo-delete}"
LOCAL_RETAIN_CLASS="${LOCAL_RETAIN_CLASS:-aileron-local-rwo-retain}"
PROBE_IMAGE="${PROBE_IMAGE:-busybox:1.37}"
PROBE_GID="${PROBE_GID:-100}"
namespace="aileron-storage-preflight-$(date +%s)"

usage() {
  echo "Usage: $0 --context NAME" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --context) context="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

test -n "${context}" || usage

kubectl_target() {
  "${KUBECTL}" --context "${context}" "$@"
}

cleanup() {
  kubectl_target delete namespace "${namespace}" --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

fail() {
  echo "Storage preflight failed: $*" >&2
  exit 1
}

assert_storage_class() {
  name="$1"
  provisioner="$2"
  reclaim_policy="$3"
  binding_mode="$4"

  actual="$(kubectl_target get storageclass "${name}" \
    -o jsonpath='{.provisioner}{"|"}{.reclaimPolicy}{"|"}{.volumeBindingMode}')"
  expected="${provisioner}|${reclaim_policy}|${binding_mode}"
  [ "${actual}" = "${expected}" ] || \
    fail "StorageClass ${name} is ${actual}; expected ${expected}"
}

node_names="$(kubectl_target get nodes \
  -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{range .status.conditions[?(@.type=="Ready")]}{.status}{end}{"\n"}{end}' |
  awk -F '|' '$2 == "True" { print $1 }')"
node_one="$(printf '%s\n' "${node_names}" | sed -n '1p')"
node_two="$(printf '%s\n' "${node_names}" | sed -n '2p')"
[ -n "${node_one}" ] || fail "no Ready Kubernetes node is available"
[ -n "${node_two}" ] || fail "at least two Ready nodes are required for the NFS cross-node probe"

assert_storage_class "${NFS_DELETE_CLASS}" nfs.csi.k8s.io Delete Immediate
assert_storage_class "${NFS_RETAIN_CLASS}" nfs.csi.k8s.io Retain Immediate
assert_storage_class "${LOCAL_DELETE_CLASS}" rancher.io/local-path Delete WaitForFirstConsumer
assert_storage_class "${LOCAL_RETAIN_CLASS}" rancher.io/local-path Retain WaitForFirstConsumer

kubectl_target create namespace "${namespace}" >/dev/null
kubectl_target label namespace "${namespace}" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted >/dev/null

cat <<EOF | kubectl_target apply -f - >/dev/null
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nfs-rwx
  namespace: ${namespace}
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ${NFS_DELETE_CLASS}
  resources:
    requests:
      storage: 64Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: nfs-writer
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_one}
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: ${PROBE_GID}
    fsGroup: ${PROBE_GID}
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${PROBE_IMAGE}
      command:
        - /bin/sh
        - -ec
        - |
          umask 0007
          test "\$(stat -c '%g' /data)" = "${PROBE_GID}"
          test "\$((0\$(stat -c '%a' /data) & 02000))" -ne 0
          mkdir /data/cross-node
          printf 'writer\n' > /data/cross-node/probe
          test "\$(stat -c '%g' /data/cross-node)" = "${PROBE_GID}"
          test "\$(stat -c '%g' /data/cross-node/probe)" = "${PROBE_GID}"
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: nfs-rwx
EOF

kubectl_target wait --for=jsonpath='{.status.phase}'=Succeeded \
  "pod/nfs-writer" -n "${namespace}" --timeout=180s >/dev/null || {
  kubectl_target describe pod nfs-writer -n "${namespace}" >&2 || true
  kubectl_target logs nfs-writer -n "${namespace}" >&2 || true
  fail "NFS writer probe did not succeed"
}

cat <<EOF | kubectl_target apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: nfs-reader
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeName: ${node_two}
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: ${PROBE_GID}
    fsGroup: ${PROBE_GID}
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${PROBE_IMAGE}
      command:
        - /bin/sh
        - -ec
        - |
          test "\$(cat /data/cross-node/probe)" = "writer"
          printf 'reader\n' >> /data/cross-node/probe
          test "\$(tail -n 1 /data/cross-node/probe)" = "reader"
          rm -rf /data/cross-node
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: nfs-rwx
EOF

kubectl_target wait --for=jsonpath='{.status.phase}'=Succeeded \
  "pod/nfs-reader" -n "${namespace}" --timeout=180s >/dev/null || {
  kubectl_target describe pod nfs-reader -n "${namespace}" >&2 || true
  kubectl_target logs nfs-reader -n "${namespace}" >&2 || true
  fail "NFS cross-node reader probe did not succeed"
}

cat <<EOF | kubectl_target apply -f - >/dev/null
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: local-rwo
  namespace: ${namespace}
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${LOCAL_DELETE_CLASS}
  resources:
    requests:
      storage: 64Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: local-writer
  namespace: ${namespace}
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/hostname: ${node_one}
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: ${PROBE_GID}
    fsGroup: ${PROBE_GID}
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${PROBE_IMAGE}
      command:
        - /bin/sh
        - -ec
        - |
          umask 0007
          dd if=/dev/zero of=/data/fsync-probe bs=4096 count=1 conv=fsync
          test "\$(stat -c '%s' /data/fsync-probe)" = "4096"
          rm /data/fsync-probe
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: local-rwo
EOF

kubectl_target wait --for=jsonpath='{.status.phase}'=Succeeded \
  "pod/local-writer" -n "${namespace}" --timeout=180s >/dev/null || {
  kubectl_target describe pod local-writer -n "${namespace}" >&2 || true
  kubectl_target logs local-writer -n "${namespace}" >&2 || true
  fail "local RWO fsync probe did not succeed"
}

echo "Storage preflight passed: NFS RWX crossed ${node_one} -> ${node_two}; local RWO fsync passed on ${node_one}"

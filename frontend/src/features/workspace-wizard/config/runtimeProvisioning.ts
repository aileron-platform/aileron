export const DEPLOYED_RUNTIME_PROVISIONER =
  import.meta.env.VITE_RUNTIME_PROVISIONER === 'kubernetes'
    ? 'kubernetes'
    : 'docker';

const parseNamespaceList = (value: string | undefined): string[] => {
  if (!value) {
    return ['default'];
  }

  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  return items.length > 0 ? items : ['default'];
};

export const KUBERNETES_ALLOWED_NAMESPACES = parseNamespaceList(
  import.meta.env.VITE_WORKSPACE_K8S_ALLOWED_NAMESPACES,
);

export const KUBERNETES_DEFAULT_NAMESPACE =
  import.meta.env.VITE_WORKSPACE_K8S_DEFAULT_NAMESPACE?.trim() ||
  KUBERNETES_ALLOWED_NAMESPACES[0] ||
  'default';

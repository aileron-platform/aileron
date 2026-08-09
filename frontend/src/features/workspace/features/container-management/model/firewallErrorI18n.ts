type FirewallErrorCode =
  | 'FIREWALL_DELIVERY_FAILED'
  | 'FIREWALL_APPLY_FAILED'
  | 'FIREWALL_DOMAIN_INVALID'
  | 'FIREWALL_DOMAIN_DUPLICATE'
  | 'FIREWALL_DOMAIN_LIMIT_EXCEEDED'
  | 'FIREWALL_ALLOWLIST_EMPTY'
  | 'FIREWALL_DOMAINS_NOT_ALLOWED'
  | 'FIREWALL_RETRY_NOT_ALLOWED'
  | 'CILIUM_NOT_ENABLED'
  | 'FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED'
  | 'FIREWALL_POLICY_APPLY_FAILED'
  | 'FIREWALL_POLICY_ENFORCEMENT_TIMEOUT'
  | 'FIREWALL_POLICY_REJECTED'
  | 'FIREWALL_POLICY_STATUS_INVALID';

export const FIREWALL_ERROR_I18N_KEYS = {
  FIREWALL_DELIVERY_FAILED:
    'workspace.containerManagement.firewall.errors.FIREWALL_DELIVERY_FAILED',
  FIREWALL_APPLY_FAILED:
    'workspace.containerManagement.firewall.errors.FIREWALL_APPLY_FAILED',
  FIREWALL_DOMAIN_INVALID:
    'workspace.containerManagement.firewall.errors.FIREWALL_DOMAIN_INVALID',
  FIREWALL_DOMAIN_DUPLICATE:
    'workspace.containerManagement.firewall.errors.FIREWALL_DOMAIN_DUPLICATE',
  FIREWALL_DOMAIN_LIMIT_EXCEEDED:
    'workspace.containerManagement.firewall.errors.FIREWALL_DOMAIN_LIMIT_EXCEEDED',
  FIREWALL_ALLOWLIST_EMPTY:
    'workspace.containerManagement.firewall.errors.FIREWALL_ALLOWLIST_EMPTY',
  FIREWALL_DOMAINS_NOT_ALLOWED:
    'workspace.containerManagement.firewall.errors.FIREWALL_DOMAINS_NOT_ALLOWED',
  FIREWALL_RETRY_NOT_ALLOWED:
    'workspace.containerManagement.firewall.errors.FIREWALL_RETRY_NOT_ALLOWED',
  CILIUM_NOT_ENABLED:
    'workspace.containerManagement.firewall.errors.CILIUM_NOT_ENABLED',
  FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED:
    'workspace.containerManagement.firewall.errors.FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED',
  FIREWALL_POLICY_APPLY_FAILED:
    'workspace.containerManagement.firewall.errors.FIREWALL_POLICY_APPLY_FAILED',
  FIREWALL_POLICY_ENFORCEMENT_TIMEOUT:
    'workspace.containerManagement.firewall.errors.FIREWALL_POLICY_ENFORCEMENT_TIMEOUT',
  FIREWALL_POLICY_REJECTED:
    'workspace.containerManagement.firewall.errors.FIREWALL_POLICY_REJECTED',
  FIREWALL_POLICY_STATUS_INVALID:
    'workspace.containerManagement.firewall.errors.FIREWALL_POLICY_STATUS_INVALID',
} as const satisfies Record<FirewallErrorCode, string>;

const isFirewallErrorCode = (value: string): value is FirewallErrorCode => (
  Object.prototype.hasOwnProperty.call(FIREWALL_ERROR_I18N_KEYS, value)
);

export const getFirewallErrorI18nKey = (
  errorCode: string | null | undefined,
): string | null => (
  errorCode && isFirewallErrorCode(errorCode)
    ? FIREWALL_ERROR_I18N_KEYS[errorCode]
    : null
);

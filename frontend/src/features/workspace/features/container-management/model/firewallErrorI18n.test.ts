import { describe, expect, it } from 'vitest';
import en from '@/shared/locales/en';
import zhTW from '@/shared/locales/zh-TW';
import { FIREWALL_ERROR_I18N_KEYS } from './firewallErrorI18n';

type LocaleTree = Record<string, unknown>;

const getByKey = (tree: LocaleTree, key: string): unknown => (
  key.split('.').reduce<unknown>((cursor, part) => {
    if (!cursor || typeof cursor !== 'object') {
      return undefined;
    }
    return (cursor as LocaleTree)[part];
  }, tree)
);

const operatorStableErrorCodes = [
  'FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED',
  'FIREWALL_POLICY_APPLY_FAILED',
  'FIREWALL_POLICY_ENFORCEMENT_TIMEOUT',
  'FIREWALL_POLICY_REJECTED',
  'FIREWALL_POLICY_STATUS_INVALID',
] as const;

describe('firewallErrorI18n', () => {
  it('maps every stable Operator firewall error code explicitly', () => {
    const unmapped = operatorStableErrorCodes.filter((errorCode) => (
      !Object.prototype.hasOwnProperty.call(FIREWALL_ERROR_I18N_KEYS, errorCode)
    ));

    expect(unmapped).toEqual([]);
  });

  it('resolves every mapped firewall error key in both locales', () => {
    const missing = Object.values(FIREWALL_ERROR_I18N_KEYS).filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });
});

import { describe, expect, it } from 'vitest';
import en from '@/shared/locales/en';
import zhTW from '@/shared/locales/zh-TW';
import { KNOWLEDGE_BASE_SHARING_ERROR_I18N_KEYS } from './knowledgeBaseSharingErrorI18n';

type LocaleTree = Record<string, unknown>;

const getByKey = (tree: LocaleTree, key: string): unknown => (
  key.split('.').reduce<unknown>((cursor, part) => {
    if (!cursor || typeof cursor !== 'object') {
      return undefined;
    }
    return (cursor as LocaleTree)[part];
  }, tree)
);

describe('knowledgeBaseSharingErrorI18n', () => {
  it('resolves every typed error key in both locales', () => {
    const missing = Object.values(KNOWLEDGE_BASE_SHARING_ERROR_I18N_KEYS).filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });
});

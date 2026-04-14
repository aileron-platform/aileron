import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ApiClient, registerLanguageProvider } from './apiClient';

describe('ApiClient', () => {
  beforeEach(() => {
    registerLanguageProvider(null);
  });

  afterEach(() => {
    registerLanguageProvider(null);
  });

  it('公開 manager host 應使用完整 API root', () => {
    const client = new ApiClient({ baseUrl: 'http://workspace-manager.localtest.me/api/v1' });

    expect((client as any).buildUrl('/workspaces/')).toBe(
      'http://workspace-manager.localtest.me/api/v1/workspaces/',
    );
  });

  it('當 baseUrl 已包含 /api/v1 時不應重複附加前綴', () => {
    const client = new ApiClient({ baseUrl: 'http://workspace-runtime.example.com/api/v1/' });

    expect((client as any).buildUrl('/files/tree')).toBe(
      'http://workspace-runtime.example.com/api/v1/files/tree',
    );
  });

  it('相對 API root 也應以完整 root 形式注入', () => {
    const client = new ApiClient({ baseUrl: '/api/v1/' });

    expect((client as any).buildUrl('/templates/')).toBe('/api/v1/templates/');
  });

  it('使用已註冊的語言 provider 附加 X-Language header', () => {
    registerLanguageProvider(() => 'en');
    const client = new ApiClient();

    expect((client as any).buildHeaders()).toMatchObject({
      'Content-Type': 'application/json',
      'X-Language': 'en',
    });
  });

  it('保留顯式傳入的 X-Language header', () => {
    registerLanguageProvider(() => 'en');
    const client = new ApiClient();

    expect((client as any).buildHeaders({ 'X-Language': 'zh-TW' })).toMatchObject({
      'Content-Type': 'application/json',
      'X-Language': 'zh-TW',
    });
  });
});

import { describe, expect, it } from 'vitest';

import { resolvePreferredWorkspaceUrl, toWebSocketUrl } from './workspacePublicUrl';

describe('workspacePublicUrl', () => {
  it('優先回傳第一個可用的 external URL', () => {
    expect(
      resolvePreferredWorkspaceUrl(
        'https://workspace-runtime-ws-1.example.com',
        'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002'
      )
    ).toBe('https://workspace-runtime-ws-1.example.com');
  });

  it('在沒有 external URL 時回退到 internal URL', () => {
    expect(
      resolvePreferredWorkspaceUrl(
        '',
        null,
        'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002'
      )
    ).toBe('http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002');
  });

  it('會將 https URL 轉成 wss WebSocket URL', () => {
    expect(toWebSocketUrl('https://workspace-browser-ws-1.example.com', '/ws')).toBe(
      'wss://workspace-browser-ws-1.example.com/ws'
    );
  });

  it('會保留 http URL 對應的 ws 協定', () => {
    expect(
      toWebSocketUrl('http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002', '/api/v1/ws')
    ).toBe('ws://workspace-runtime-ws-1.team-a.svc.cluster.local:3002/api/v1/ws');
  });
});

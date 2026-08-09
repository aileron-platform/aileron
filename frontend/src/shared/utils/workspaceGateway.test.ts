import { describe, expect, it } from 'vitest';
import {
  buildWorkspaceGatewayPath,
  toSameOriginWebSocketUrl,
} from './workspaceGateway';

const WORKSPACE_ID = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';

describe('workspaceGateway', () => {
  it('builds canonical same-origin paths for execution-plane targets', () => {
    expect(buildWorkspaceGatewayPath(WORKSPACE_ID, 'runtime')).toBe(
      `/workspaces/${WORKSPACE_ID}/runtime`,
    );
    expect(buildWorkspaceGatewayPath(WORKSPACE_ID, 'browser', '/ws')).toBe(
      `/workspaces/${WORKSPACE_ID}/browser/ws`,
    );
    expect(buildWorkspaceGatewayPath(WORKSPACE_ID, 'canvas', '/slides/1')).toBe(
      `/workspaces/${WORKSPACE_ID}/canvas/slides/1`,
    );
  });

  it('rejects non-canonical workspace identifiers', () => {
    expect(() => buildWorkspaceGatewayPath('../runtime', 'runtime')).toThrow(
      'WORKSPACE_GATEWAY_ID_INVALID',
    );
    expect(() => buildWorkspaceGatewayPath('workspace-1', 'runtime')).toThrow(
      'WORKSPACE_GATEWAY_ID_INVALID',
    );
  });

  it('converts only a same-origin path to the current WebSocket origin', () => {
    expect(toSameOriginWebSocketUrl(
      `/workspaces/${WORKSPACE_ID}/runtime/api/v1/threads/events`,
      'https://aileron.example.test',
    )).toBe(
      `wss://aileron.example.test/workspaces/${WORKSPACE_ID}/runtime/api/v1/threads/events`,
    );
    expect(() => toSameOriginWebSocketUrl('https://runtime.example.test/ws')).toThrow(
      'WORKSPACE_GATEWAY_PATH_INVALID',
    );
  });
});

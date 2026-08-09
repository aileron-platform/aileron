import {
  apiClient,
  registerExecutionGrantProvider,
  registerExecutionGrantRejectionHandler,
} from '@/shared/api/apiClient';
import { managerSessionService } from './ManagerSessionService';

export type RuntimeAction =
  | 'agent'
  | 'browser_automation'
  | 'runtime_read'
  | 'runtime_write'
  | 'workspace_settings'
  | 'terminal';

interface RuntimeTarget {
  workspaceId: string;
}

interface CachedGrant {
  token: string;
  refreshAt: number;
}

interface RuntimeGeneration {
  runtimeInstanceId: string;
  runtimeAccessRevision: number;
}

const targetKey = (value: string): string => {
  const url = new URL(value, window.location.origin);
  const gateway = url.pathname.match(
    /^\/workspaces\/[0-9a-f-]+\/(?:runtime|browser|canvas)(?:\/|$)/,
  );
  return gateway ? `${url.origin}${gateway[0].replace(/\/$/, '')}` : url.origin;
};

const classifyRuntimeAction = (method: string, rawPath: string): RuntimeAction => {
  const path = rawPath.split('?', 1)[0];
  if (path.startsWith('/api/v1/threads') || path.startsWith('/api/v1/audio/')) {
    return 'agent';
  }
  if (path.startsWith('/api/v1/client-browser-relay')) return 'browser_automation';
  if (
    path.includes('/agent-settings/')
    || path.includes('/mcp-servers')
    || path.includes('/mcp-import')
    || path.includes('/claude-code/settings')
    || path.includes('/codex/config')
  ) {
    return 'workspace_settings';
  }
  return method.toUpperCase() === 'GET' ? 'runtime_read' : 'runtime_write';
};

class ExecutionGrantBroker {
  private readonly targets = new Map<string, RuntimeTarget>();
  private readonly cache = new Map<string, CachedGrant>();
  private readonly pending = new Map<string, Promise<string>>();

  constructor() {
    registerExecutionGrantProvider(({ targetUrl, method, path }) => this.getGrant(
      targetUrl,
      'workspace-runtime',
      classifyRuntimeAction(method, path),
    ));
    registerExecutionGrantRejectionHandler(({ targetUrl }) => {
      const target = this.targets.get(targetKey(targetUrl));
      if (!target) return false;
      this.invalidateWorkspace(target.workspaceId);
      return true;
    });
  }

  registerTarget(targetUrl: string | null | undefined, workspaceId: string): void {
    if (!targetUrl || !workspaceId) return;
    this.targets.set(targetKey(targetUrl), { workspaceId });
  }

  async getGrant(
    targetUrl: string,
    audience: 'workspace-runtime' | 'workspace-terminal',
    action: RuntimeAction | readonly RuntimeAction[],
    workspaceId?: string,
  ): Promise<string> {
    const target = this.targets.get(targetKey(targetUrl));
    const resolvedWorkspaceId = workspaceId || target?.workspaceId;
    if (!resolvedWorkspaceId) throw new Error('EXECUTION_GRANT_TARGET_UNKNOWN');
    const generation = await this.resolveRuntimeGeneration(resolvedWorkspaceId);
    const actions = [...(Array.isArray(action) ? action : [action])].sort();
    const cacheKey = [
      resolvedWorkspaceId,
      targetKey(targetUrl),
      generation.runtimeInstanceId,
      generation.runtimeAccessRevision,
      audience,
      actions.join(','),
    ].join(':');
    const cached = this.cache.get(cacheKey);
    if (cached && Date.now() < cached.refreshAt) return cached.token;
    const activeRequest = this.pending.get(cacheKey);
    if (activeRequest) return activeRequest;
    const request = this.issue(resolvedWorkspaceId, generation, audience, actions)
      .then((token) => {
        this.cache.set(cacheKey, { token, refreshAt: Date.now() + 50_000 });
        return token;
      })
      .finally(() => this.pending.delete(cacheKey));
    this.pending.set(cacheKey, request);
    return request;
  }

  invalidateWorkspace(workspaceId: string): void {
    for (const key of this.cache.keys()) {
      if (key.startsWith(`${workspaceId}:`)) this.cache.delete(key);
    }
  }

  private async issue(
    workspaceId: string,
    generation: RuntimeGeneration,
    audience: 'workspace-runtime' | 'workspace-terminal',
    actions: RuntimeAction[],
  ): Promise<string> {
    let csrfToken = managerSessionService.getCsrfToken();
    if (!csrfToken) {
      await managerSessionService.bootstrap();
      csrfToken = managerSessionService.getCsrfToken();
    }
    if (!csrfToken) throw new Error('MANAGER_SESSION_REQUIRED');
    const payload = await apiClient.post<{ grant?: string; expiresIn?: number }>(
      `/workspaces/${encodeURIComponent(workspaceId)}/execution-grants`,
      {
        runtimeInstanceId: generation.runtimeInstanceId,
        audience,
        actions,
      },
    );
    if (!payload.grant || payload.expiresIn !== 60) {
      throw new Error('EXECUTION_GRANT_RESPONSE_INVALID');
    }
    return payload.grant;
  }

  private async resolveRuntimeGeneration(workspaceId: string): Promise<RuntimeGeneration> {
    const availability = await apiClient.get<{
      runtimeInstanceId?: string | null;
      runtimeAccessDesiredRevision?: number;
    }>(`/workspaces/${encodeURIComponent(workspaceId)}/availability`);
    if (!availability.runtimeInstanceId) throw new Error('RUNTIME_INSTANCE_UNAVAILABLE');
    if (
      !Number.isInteger(availability.runtimeAccessDesiredRevision)
      || (availability.runtimeAccessDesiredRevision ?? -1) < 0
    ) {
      throw new Error('RUNTIME_ACCESS_REVISION_UNAVAILABLE');
    }
    return {
      runtimeInstanceId: availability.runtimeInstanceId,
      runtimeAccessRevision: availability.runtimeAccessDesiredRevision as number,
    };
  }
}

export const executionGrantBroker = new ExecutionGrantBroker();

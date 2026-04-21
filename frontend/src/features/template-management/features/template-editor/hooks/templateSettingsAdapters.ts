import type { TemplateHook, TemplateMcpServer } from '@/shared/types/templates';
import type { HookFormValue, McpServerFormValue } from '../formTypes';

export const mapTemplateHooksToFormValues = (templateHooks: TemplateHook[]): HookFormValue[] => {
  const groupedHooks = templateHooks.reduce<Record<string, TemplateHook[]>>((acc, hook) => {
    if (!acc[hook.event]) {
      acc[hook.event] = [];
    }
    acc[hook.event].push(hook);
    return acc;
  }, {});

  return Object.entries(groupedHooks).map(([event, eventHooks]) => ({
    localId: `event-${event}`,
    event,
    matchers: eventHooks.map((hook) => ({
      matcher: hook.matcher ?? '*',
      hooks: [{
        type: 'command',
        command: hook.command ?? hook.script ?? '',
        timeout: hook.timeout ?? 30,
      }],
    })),
  }));
};

export const mapTemplateMcpServersToFormValues = (
  templateServers: TemplateMcpServer[],
): McpServerFormValue[] => {
  return templateServers.map((server) => ({
    localId: server.id,
    name: server.name,
    type: server.type,
    command: server.command ?? '',
    argsText: server.args?.join('\n') ?? '',
    url: server.url ?? '',
    description: server.description ?? '',
    envText: server.env
      ? Object.entries(server.env).map(([key, value]) => `${key}=${value}`).join('\n')
      : '',
    headersText: server.headers
      ? Object.entries(server.headers).map(([key, value]) => `${key}: ${value}`).join('\n')
      : '',
  }));
};

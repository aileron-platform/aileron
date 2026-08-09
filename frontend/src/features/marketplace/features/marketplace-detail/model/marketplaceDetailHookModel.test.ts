import { describe, expect, it } from 'vitest';
import {
  marketplaceHookCardEntriesFromItem,
  normalizeMarketplaceHookAction,
} from './marketplaceDetailHookModel';
import type { MarketplaceFeatureContentItem } from '@/features/marketplace/model/marketplaceTypes';

describe('marketplaceDetailHookModel', () => {
  it('builds hook card entries from legacy matcher data', () => {
    const item: MarketplaceFeatureContentItem = {
      id: 'hook-a',
      name: 'PreToolUse',
      description: 'Runs before tools',
      data: {
        event: 'PreToolUse',
        matchers: [{
          matcher: 'Bash',
          sequential: true,
          hooks: [{
            type: 'command',
            name: 'Audit',
            command: 'echo audit',
            shell: 'bash',
            async: true,
          }],
        }],
      },
    };

    expect(marketplaceHookCardEntriesFromItem(item)).toEqual([{
      id: 'hook-a:PreToolUse',
      hook: item,
      eventName: 'PreToolUse',
      sourceDescription: 'Runs before tools',
      matchers: [{
        event: 'PreToolUse',
        matcher: 'Bash',
        sequential: true,
        hooks: [{
          type: 'command',
          name: 'Audit',
          description: undefined,
          command: 'echo audit',
          timeout: undefined,
          statusMessage: undefined,
          if: undefined,
          shell: 'bash',
          async: true,
          asyncRewake: undefined,
        }],
      }],
    }]);
  });

  it('builds one card per native hook event', () => {
    const item: MarketplaceFeatureContentItem = {
      id: 'hook-native',
      name: 'hooks.json',
      data: {
        hooks: {
          PreToolUse: [{ matcher: 'Write', hooks: [{ type: 'http', url: 'https://example.local/hook' }] }],
          Stop: [{ hooks: [{ type: 'prompt', prompt: 'Summarize' }] }],
        },
      },
    };

    const entries = marketplaceHookCardEntriesFromItem(item);

    expect(entries.map(entry => entry.id)).toEqual(['hook-native:PreToolUse', 'hook-native:Stop']);
    expect(entries[0].matchers[0].hooks[0]).toMatchObject({
      type: 'http',
      url: 'https://example.local/hook',
    });
    expect(entries[1].matchers[0].matcher).toBe('*');
  });

  it('normalizes marketplace hook action types for shared hook cards', () => {
    expect(normalizeMarketplaceHookAction({ type: 'mcp_tool', server: 'github', tool: 'search' })).toMatchObject({
      type: 'mcp_tool',
      server: 'github',
      tool: 'search',
    });
    expect(normalizeMarketplaceHookAction({ type: 'agent', prompt: 'Review this' })).toMatchObject({
      type: 'agent',
      prompt: 'Review this',
    });
    expect(normalizeMarketplaceHookAction({ command: 'npm test', shell: 'fish' })).toMatchObject({
      type: 'command',
      command: 'npm test',
      shell: undefined,
    });
  });
});

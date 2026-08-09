import { describe, expect, it } from 'vitest';
import enNavigation from './en/modules/workspace/navigation';
import zhTWNavigation from './zh-TW/modules/workspace/navigation';
import enClaudeCode from './en/modules/workspace/claudeCode';
import zhTWClaudeCode from './zh-TW/modules/workspace/claudeCode';
import enCodex from './en/modules/workspace/codex';
import zhTWCodex from './zh-TW/modules/workspace/codex';
import enAgentSettings from './en/modules/workspace/agentSettings';
import zhTWAgentSettings from './zh-TW/modules/workspace/agentSettings';

describe('workspace settings labels', () => {
  it('keeps provider main navigation labels localized', () => {
    expect(enNavigation.main.claudeCodeSettings).toBe('Claude Code Settings');
    expect(enNavigation.main.codexSettings).toBe('Codex Settings');

    expect(zhTWNavigation.main.claudeCodeSettings).toBe('Claude Code \u8a2d\u5b9a');
    expect(zhTWNavigation.main.codexSettings).toBe('Codex \u8a2d\u5b9a');
  });

  it('keeps Claude Code and Codex settings submenus in English', () => {
    expect(enNavigation.sub.claudeCodeSettings.settings).toBe('Settings');
    expect(enAgentSettings.common.subViews.plugins).toBe('Plugins');
    expect(enAgentSettings.common.subViews.settings).toBe('Settings');

    expect(zhTWNavigation.sub.claudeCodeSettings.settings).toBe('Settings');
    expect(zhTWAgentSettings.common.subViews.plugins).toBe('Plugins');
    expect(zhTWAgentSettings.common.subViews.settings).toBe('Settings');
  });

  it('keeps settings page titles in English for every locale', () => {
    expect(enClaudeCode.settings.header.title).toBe('Settings');
    expect(enCodex.settings.header.title).toBe('Settings');

    expect(zhTWClaudeCode.settings.header.title).toBe('Settings');
    expect(zhTWCodex.settings.header.title).toBe('Settings');
  });

  it('keeps provider document and settings section titles in English for zh-TW', () => {
    expect(zhTWClaudeCode.documents.meta['slash-commands'].title).toBe('Slash Commands');
    expect(zhTWClaudeCode.documents.meta['output-styles'].title).toBe('Output Styles');
    expect(zhTWClaudeCode.documents.meta.subagents.title).toBe('Subagents');
    expect(zhTWClaudeCode.documents.meta.memory.title).toBe('Memory');

    expect(zhTWAgentSettings.codex.plugins.title).toBe('Plugins');
    expect(zhTWAgentSettings.codex.documents.meta.prompts.title).toBe('Prompts');
    expect(zhTWAgentSettings.codex.documents.meta.subagents.title).toBe('Subagents');
    expect(zhTWAgentSettings.codex.documents.meta.rules.title).toBe('Rules');

    expect(zhTWAgentSettings.common.hooks.header.title).toBe('Hooks');
    expect(zhTWAgentSettings.common.mcp.header.title).toBe('Model Context Protocol');
    expect(zhTWAgentSettings.common.slashCommands.pageTitle).toBe('Slash Commands');
    expect(zhTWAgentSettings.common.documents.meta['slash-commands'].title).toBe('Slash Commands');
    expect(zhTWAgentSettings.common.documents.meta.subagents.title).toBe('Subagents');
    expect(zhTWAgentSettings.common.subagents.pageTitle).toBe('Subagents');
  });
});

import { describe, expect, it } from 'vitest';
import enAgentSettings from './en/modules/workspace/agentSettings';
import zhTWAgentSettings from './zh-TW/modules/workspace/agentSettings';

describe('workspace agent settings locales', () => {
  it('defines common hook dialog labels in every locale', () => {
    expect(enAgentSettings.common.hooks.dialog.name.label).toBe('Name *');
    expect(enAgentSettings.common.hooks.dialog.name.placeholder).toBe('e.g. Format TypeScript files');
    expect(enAgentSettings.common.hooks.dialog.matcher.sequentialLabel).toBe('Run actions sequentially');
    expect(enAgentSettings.common.hooks.dialog.matcher.sequentialHelp).toBe('Run matched actions in order instead of concurrently.');
    expect(zhTWAgentSettings.common.hooks.dialog.name.label).toBe('名稱 *');
    expect(zhTWAgentSettings.common.hooks.dialog.name.placeholder).toBe('例如：格式化 TypeScript 檔案');
    expect(zhTWAgentSettings.common.hooks.dialog.matcher.sequentialLabel).toBe('依序執行 actions');
    expect(zhTWAgentSettings.common.hooks.dialog.matcher.sequentialHelp).toBe('讓符合條件的 actions 依序執行，而不是並行執行。');
  });
});

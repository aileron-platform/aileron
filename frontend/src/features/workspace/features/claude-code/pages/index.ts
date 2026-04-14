// Claude 專有頁面
export { default as SettingsPage } from './SettingsPage';
export { default as OutputStylesPage } from './OutputStylesPage';
export { default as SubagentsPage } from './SubagentsPage';
export { default as ScriptsPage } from './ScriptsPage';
export { default as MemoryPage } from './MemoryPage';

// 共用頁面（同時從 cli-settings 匯出，支援 apiPrefix prop）
export { default as MCPSettingsPage } from './MCPSettingsPage';
export { default as HooksSettingsPage } from './HooksSettingsPage';
export { default as SlashCommandsPage } from './SlashCommandsPage';
export { default as SkillsPage } from './SkillsPage';

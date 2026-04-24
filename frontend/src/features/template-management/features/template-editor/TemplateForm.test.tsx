import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TemplateForm from './TemplateForm';
import type { TemplateFormValues } from './formTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'template.editor.tabs.basic': '基本資訊',
        'template.common.features.agentsMd': 'AGENTS.md',
        'template.common.features.hooks': 'Hooks',
        'template.common.features.mcp': 'MCP',
        'template.common.features.agents': 'Agents',
        'template.common.features.commands': 'Commands',
        'template.common.features.outputStyle': 'Output Style',
        'template.common.features.skills': 'Skills',
        'template.common.features.scripts': 'Scripts',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('./sections/BasicInfoSection', () => ({
  default: () => <div>basic-section</div>,
}));

vi.mock('./sections/McpServersSection', () => ({
  default: () => <div>mcp-section</div>,
}));

vi.mock('./sections/CommandsSection', () => ({
  default: () => <div>slash-section</div>,
}));

vi.mock('./sections/HooksSection', () => ({
  default: () => <div>hooks-section</div>,
}));

vi.mock('./sections/AgentsSection', () => ({
  default: () => <div>subagent-section</div>,
}));

vi.mock('./sections/OutputStyleSection', () => ({
  default: () => <div>outputstyle-section</div>,
}));

vi.mock('./sections/DocsSection', () => ({
  default: () => <div>docs-section</div>,
}));

vi.mock('./sections/SkillsSection', () => ({
  default: () => <div>skills-section</div>,
}));

vi.mock('./sections/ScriptsSection', () => ({
  default: () => <div>scripts-section</div>,
}));

const values: TemplateFormValues = {
  templateId: 'tpl-1',
  name: 'Template 1',
  description: '',
  version: '1.0.0',
  authorName: '',
  authorEmail: '',
  authorUrl: '',
  keywords: [],
  categoryId: '',
  documentation: '',
  agentsMd: '',
  isActive: true,
  initCommands: '',
  mcpServers: [{ localId: 'm1', name: 'server-1', type: 'stdio', command: 'run', argsText: '', url: '', description: '', envText: '', headersText: '' }],
  commands: [{ localId: 's1', fileName: 'foo.md', content: 'x', description: '' }],
  hooks: [{ localId: 'h1', event: 'PreToolUse', matchers: [] }],
  agents: [{ localId: 'a1', fileName: 'worker.md', content: 'x', description: '' }],
  outputStyle: [{ localId: 'o1', fileName: 'style.md', content: 'x', description: '' }],
  skills: [{ localId: 'sk1', path: '/skill.md', content: 'x' }],
  scripts: [{ localId: 'sc1', path: '/build.sh', content: 'echo hi' }],
};

describe('TemplateForm', () => {
  it('renders shared top tabs with i18n labels and count badges', () => {
    render(
      <TemplateForm
        values={values}
        onChange={vi.fn()}
        onAddKeyword={vi.fn()}
        onRemoveKeyword={vi.fn()}
        activeTab="basic"
        setActiveTab={vi.fn()}
      />,
    );

    expect(screen.getByRole('tab', { name: /基本資訊/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /agents\.md/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /mcp 1/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /hooks 1/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /commands 1/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /agents 1/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /output style 1/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /skills 1/i })).toBeInTheDocument();
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
  });
});

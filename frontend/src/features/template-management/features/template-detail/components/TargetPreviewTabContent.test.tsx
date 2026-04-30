import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { TargetPreviewTabContent } from './TargetPreviewTabContent';

const getTemplateCompilePreviewMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'template.common.targets.claudeCode': 'Claude Code',
        'template.common.targets.codex': 'Codex',
        'template.common.targets.gemini': 'Gemini',
        'template.common.targets.opencode': 'OpenCode',
        'template.detail.targetPreview.targetLabel': '目標 CLI',
        'template.detail.targetPreview.description': '預覽不同 target 的編譯結果',
        'template.detail.targetPreview.loading': '載入編譯預覽中...',
        'template.detail.targetPreview.sections.files': '編譯輸出',
        'template.detail.targetPreview.sections.warnings': 'Warnings',
        'template.detail.targetPreview.sections.unsupported': 'Unsupported',
        'template.detail.targetPreview.sections.degradation': 'Degradation',
        'template.detail.targetPreview.file.sourceLabel': '來源',
        'template.detail.targetPreview.file.contentPreviewLabel': '內容預覽',
        'template.detail.targetPreview.emptyFiles': '沒有檔案',
        'template.detail.targetPreview.states.none': '目前沒有項目。',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/features/template-management/api/templateApi', () => ({
  getTemplateCompilePreview: (...args: unknown[]) => getTemplateCompilePreviewMock(...args),
}));

describe('TargetPreviewTabContent', () => {
  beforeEach(() => {
    getTemplateCompilePreviewMock.mockReset();
  });

  it('renders compile preview and switches target', async () => {
    getTemplateCompilePreviewMock.mockImplementation(async (_templateId: string, target: string) => {
      if (target === 'codex') {
        return {
          target: 'codex',
          files: [
            {
              path: 'AGENTS.md',
              source: 'agents.md',
              content: '# Codex',
            },
          ],
          warnings: [
            {
              feature: 'outputStyle',
              target: 'codex',
              message: 'fallback',
            },
          ],
          unsupported: [],
          degradationNotes: [
            {
              feature: 'outputStyle',
              target: 'codex',
              message: 'fallback',
            },
          ],
          installHints: {},
        };
      }

      return {
        target: 'claude-code',
        files: [
          {
            path: 'CLAUDE.md',
            source: 'agents.md',
            content: '# Claude',
          },
        ],
        warnings: [],
        unsupported: [],
        degradationNotes: [],
        installHints: {},
      };
    });

    render(<TargetPreviewTabContent templateId="tpl-1" defaultTarget="claude-code" />);

    expect(await screen.findByText('CLAUDE.md')).toBeInTheDocument();
    expect(getTemplateCompilePreviewMock).toHaveBeenCalledWith('tpl-1', 'claude-code');

    await userEvent.click(screen.getByRole('button', { name: 'Codex' }));

    await waitFor(() => {
      expect(getTemplateCompilePreviewMock).toHaveBeenCalledWith('tpl-1', 'codex');
    });
    expect(await screen.findByText('AGENTS.md')).toBeInTheDocument();
    expect(screen.getAllByText('fallback').length).toBeGreaterThan(0);
  });

  it('renders localized error state when preview api fails', async () => {
    getTemplateCompilePreviewMock.mockRejectedValue(new Error('preview failed'));

    render(<TargetPreviewTabContent templateId="tpl-2" defaultTarget="claude-code" />);

    expect(await screen.findByText('preview failed')).toBeInTheDocument();
  });

  it('renders unsupported items for target preview', async () => {
    getTemplateCompilePreviewMock.mockResolvedValue({
      target: 'opencode',
      files: [],
      warnings: [],
      unsupported: [
        {
          feature: 'hooks',
          target: 'opencode',
          message: 'hooks are not supported',
        },
      ],
      degradationNotes: [],
      installHints: {},
    });

    render(<TargetPreviewTabContent templateId="tpl-3" defaultTarget="opencode" />);

    expect(await screen.findByText('hooks are not supported')).toBeInTheDocument();
    expect(screen.getByText('沒有檔案')).toBeInTheDocument();
  });
});

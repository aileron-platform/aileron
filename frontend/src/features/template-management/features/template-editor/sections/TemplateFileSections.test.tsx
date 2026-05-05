import React from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SkillsSection from './SkillsSection';

const templateFileManagerMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'template.common.features.skills': 'Skills',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('./TemplateFileManager', () => ({
  default: (props: unknown) => {
    templateFileManagerMock(props);
    return <div data-testid="template-file-manager" />;
  },
}));

describe('TemplateFile sections', () => {
  beforeEach(() => {
    templateFileManagerMock.mockReset();
  });

  it('SkillsSection 將技能檔案掛到 TemplateFileManager', () => {
    const onSkillsChange = vi.fn();
    render(
      <SkillsSection
        skills={[]}
        onSkillsChange={onSkillsChange}
        templateId="tpl-1"
      />
    );

    expect(templateFileManagerMock).toHaveBeenCalledTimes(1);
    expect(templateFileManagerMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        templateId: 'tpl-1',
        basePath: 'skills',
        title: 'Skills',
        onFilesChange: expect.any(Function),
      }),
    );

    const onFilesChange = templateFileManagerMock.mock.calls[0][0].onFilesChange as (files: Array<{
      type: 'file' | 'directory';
      name: string;
      content?: string;
      path: string;
    }>) => void;

    onFilesChange([
      { type: 'file', name: 'alpha.md', content: 'A', path: '/alpha.md' },
      { type: 'directory', name: 'nested', path: '/nested' },
    ]);

    expect(onSkillsChange).toHaveBeenCalledTimes(1);
    expect(onSkillsChange.mock.calls[0][0]).toEqual([
      expect.objectContaining({
        fileName: 'alpha.md',
        content: 'A',
        path: '/alpha.md',
      }),
    ]);
  });
});

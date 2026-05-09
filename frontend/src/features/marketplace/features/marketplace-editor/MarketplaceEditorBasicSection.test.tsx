import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MarketplaceEditorBasicSection } from './MarketplaceEditorBasicSection';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange, placeholder }: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder ?? 'markdown-editor'}
      value={value}
      onChange={event => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  CodeTextEditor: ({ content, onContentChange, fileName }: {
    content: string;
    onContentChange: (content: string) => void;
    fileName: string;
  }) => (
    <textarea
      aria-label={fileName}
      value={content}
      onChange={event => onContentChange(event.target.value)}
    />
  ),
}));

const renderBasicSection = () => {
  const callbacks = {
    onPackageIdChange: vi.fn(),
    onDisplayNameChange: vi.fn(),
    onDescriptionChange: vi.fn(),
    onRequiredDraftChange: vi.fn(),
    onReadmeChange: vi.fn(),
    onProviderGuidanceChange: vi.fn(),
    onDirty: vi.fn(),
  };

  render(
    <MarketplaceEditorBasicSection
      mode="create"
      provider="codex"
      packageId="review-bot"
      displayName="Review Bot"
      description="Reviews code"
      detail={null}
      {...callbacks}
    />,
  );

  return callbacks;
};

describe('MarketplaceEditorBasicSection', () => {
  it('emits required draft updates when the package id changes', async () => {
    const callbacks = renderBasicSection();

    fireEvent.change(screen.getByPlaceholderText('marketplace.editor.fields.packageIdPlaceholder'), {
      target: { value: 'reviewer' },
    });

    expect(callbacks.onPackageIdChange).toHaveBeenCalledWith('reviewer');
    expect(callbacks.onDisplayNameChange).toHaveBeenCalledWith('reviewer');
    expect(callbacks.onDirty).toHaveBeenCalled();
    await waitFor(() => {
      expect(callbacks.onRequiredDraftChange).toHaveBeenLastCalledWith(
        expect.objectContaining({
          packageName: 'reviewer',
          manifestName: 'reviewer',
          sourcePath: './plugins/reviewer',
        }),
      );
    });
  });

  it('forwards README edits through the extracted basic section', () => {
    const callbacks = renderBasicSection();

    fireEvent.change(screen.getByLabelText('marketplace.editor.packageSections.readme.placeholder'), {
      target: { value: '# Updated' },
    });

    expect(callbacks.onReadmeChange).toHaveBeenCalledWith('# Updated');
    expect(callbacks.onDirty).toHaveBeenCalled();
  });
});

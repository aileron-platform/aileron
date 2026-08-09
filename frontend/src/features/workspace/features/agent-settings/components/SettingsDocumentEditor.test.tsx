import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { SettingsDocumentEditor } from './SettingsDocumentEditor';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      aria-label="markdown-editor"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/monaco/LocalizedMonacoEditor', () => ({
  LocalizedMonacoEditor: ({
    language,
    value,
    onChange,
  }: {
    language: string;
    value: string;
    onChange: (value: string | undefined) => void;
  }) => (
    <textarea
      aria-label={`monaco-${language}`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

describe('SettingsDocumentEditor', () => {
  it('uses the markdown editor for markdown documents', () => {
    const onChange = vi.fn();

    render(
      <SettingsDocumentEditor
        value="# Rules"
        format="markdown"
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByLabelText('markdown-editor'), {
      target: { value: '# Updated' },
    });

    expect(onChange).toHaveBeenCalledWith('# Updated');
  });

  it.each([
    ['toml', 'toml'],
    ['json', 'json'],
    ['starlark', 'python'],
  ] as const)('maps %s documents to Monaco language %s', (format, language) => {
    render(
      <SettingsDocumentEditor
        value="content"
        format={format}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(`monaco-${language}`)).toBeInTheDocument();
  });
});

import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ResolvedThemeProvider } from '@/shared/contexts/ResolvedThemeContext';
import { CodeTextEditor } from './CodeTextEditor';

const monacoMock = vi.hoisted(() => ({
  selectionListener: null as ((event: {
    selection: {
      isEmpty: () => boolean;
      startLineNumber: number;
      endLineNumber: number;
      endColumn: number;
    };
  }) => void) | null,
  disposeSelectionListener: vi.fn(),
  onDidChangeCursorSelection: vi.fn(),
}));

vi.mock('@/shared/components/monaco/disableMonacoDiagnostics', () => ({
  disableMonacoDiagnostics: vi.fn(),
}));

vi.mock('@/shared/components/monaco/LocalizedMonacoEditor', () => ({
  LocalizedMonacoEditor: ({
    onMount,
    theme,
    value,
  }: {
    onMount?: (editor: unknown, monaco: unknown) => void;
    theme?: string;
    value?: string;
  }) => {
    React.useEffect(() => {
      onMount?.({
        onDidChangeCursorSelection: monacoMock.onDidChangeCursorSelection,
      }, {});
    }, [onMount]);

    return (
      <textarea
        data-testid="code-text-editor"
        data-theme={theme}
        value={value ?? ''}
        readOnly
      />
    );
  },
}));

const renderEditor = (
  theme?: 'light' | 'dark',
  onSelectionChange = vi.fn(),
) => {
  const editor = (
    <CodeTextEditor
      filePath="/src/example.ts"
      fileName="example.ts"
      content="const value = 1;"
      onContentChange={vi.fn()}
      onSelectionChange={onSelectionChange}
    />
  );

  return render(
    theme ? <ResolvedThemeProvider value={theme}>{editor}</ResolvedThemeProvider> : editor,
  );
};

describe('CodeTextEditor resolved theme', () => {
  beforeEach(() => {
    monacoMock.selectionListener = null;
    monacoMock.disposeSelectionListener.mockReset();
    monacoMock.onDidChangeCursorSelection.mockReset();
    monacoMock.onDidChangeCursorSelection.mockImplementation((listener) => {
      monacoMock.selectionListener = listener;
      return { dispose: monacoMock.disposeSelectionListener };
    });
  });

  it('uses the light Monaco theme when no provider overrides the shared fallback', () => {
    renderEditor();

    expect(screen.getByTestId('code-text-editor')).toHaveAttribute('data-theme', 'vs');
  });

  it('uses the dark Monaco theme from the shared resolved-theme context', () => {
    renderEditor('dark');

    expect(screen.getByTestId('code-text-editor')).toHaveAttribute('data-theme', 'vs-dark');
  });

  it('reports distinct non-empty line selections and disposes the Monaco listener', () => {
    const onSelectionChange = vi.fn();
    const view = renderEditor('light', onSelectionChange);
    const selection = {
      isEmpty: () => false,
      startLineNumber: 12,
      endLineNumber: 18,
      endColumn: 4,
    };

    act(() => {
      monacoMock.selectionListener?.({ selection });
      monacoMock.selectionListener?.({ selection });
    });

    expect(onSelectionChange).toHaveBeenCalledTimes(1);
    expect(onSelectionChange).toHaveBeenCalledWith({
      filePath: '/src/example.ts',
      fileName: 'example.ts',
      startLine: 12,
      endLine: 18,
    });

    act(() => {
      monacoMock.selectionListener?.({
        selection: {
          ...selection,
          isEmpty: () => true,
        },
      });
      monacoMock.selectionListener?.({ selection });
    });

    expect(onSelectionChange).toHaveBeenCalledTimes(2);

    act(() => {
      monacoMock.selectionListener?.({
        selection: {
          ...selection,
          endColumn: 1,
        },
      });
    });

    expect(onSelectionChange).toHaveBeenLastCalledWith({
      filePath: '/src/example.ts',
      fileName: 'example.ts',
      startLine: 12,
      endLine: 17,
    });

    view.unmount();
    expect(monacoMock.disposeSelectionListener).toHaveBeenCalled();
  });
});

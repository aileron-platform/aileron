import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarkdownEditor } from './MarkdownEditor';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      if (key === 'common.markdownEditor.charCount') {
        return `Characters: ${values?.count ?? 0}`;
      }
      return key;
    },
  }),
}));

const TestMarkdownEditor: React.FC<{ initialValue: string }> = ({ initialValue }) => {
  const [value, setValue] = React.useState(initialValue);
  return (
    <MarkdownEditor
      value={value}
      onChange={setValue}
      placeholder="editor"
    />
  );
};

const setup = (initialValue: string) => {
  render(<TestMarkdownEditor initialValue={initialValue} />);
  const textarea = screen.getByPlaceholderText('editor') as HTMLTextAreaElement;
  return { textarea };
};

const selectRange = (textarea: HTMLTextAreaElement, start: number, end: number) => {
  textarea.focus();
  textarea.setSelectionRange(start, end);
};

const clickToolbar = (label: string) => {
  fireEvent.click(screen.getByRole('button', { name: label }));
};

describe('MarkdownEditor commands', () => {
  it('wraps and unwraps selected text with bold markers', async () => {
    const { textarea } = setup('alpha');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.bold');

    await waitFor(() => expect(textarea).toHaveValue('**alpha**'));
    selectRange(textarea, 2, 7);

    clickToolbar('common.markdownEditor.toolbar.bold');

    await waitFor(() => expect(textarea).toHaveValue('alpha'));
  });

  it('wraps and unwraps selected text with italic markers', async () => {
    const { textarea } = setup('alpha');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.italic');

    await waitFor(() => expect(textarea).toHaveValue('*alpha*'));
    selectRange(textarea, 1, 6);

    clickToolbar('common.markdownEditor.toolbar.italic');

    await waitFor(() => expect(textarea).toHaveValue('alpha'));
  });

  it('does not treat bold markers as italic markers', async () => {
    const { textarea } = setup('**alpha**');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.italic');

    await waitFor(() => expect(textarea).toHaveValue('***alpha***'));
  });

  it('wraps and unwraps selected text with link syntax', async () => {
    const { textarea } = setup('alpha');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.link');

    await waitFor(() => expect(textarea).toHaveValue('[alpha](https://example.com)'));
    selectRange(textarea, 1, 6);

    clickToolbar('common.markdownEditor.toolbar.link');

    await waitFor(() => expect(textarea).toHaveValue('alpha'));
  });

  it('inserts placeholders for empty inline selections', async () => {
    const { textarea } = setup('');
    selectRange(textarea, 0, 0);

    clickToolbar('common.markdownEditor.toolbar.bold');

    await waitFor(() => expect(textarea).toHaveValue('**common.markdownEditor.placeholders.bold**'));
  });

  it('handles code, image, and quote toolbar commands', async () => {
    const { textarea } = setup('alpha');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.code');

    await waitFor(() => expect(textarea).toHaveValue('`alpha`'));

    selectRange(textarea, 1, 6);
    clickToolbar('common.markdownEditor.toolbar.code');
    await waitFor(() => expect(textarea).toHaveValue('alpha'));

    selectRange(textarea, 0, textarea.value.length);
    clickToolbar('common.markdownEditor.toolbar.image');
    await waitFor(() => expect(textarea).toHaveValue('![alpha](https://image.url)'));

    selectRange(textarea, 0, textarea.value.length);
    clickToolbar('common.markdownEditor.toolbar.quote');
    await waitFor(() => expect(textarea).toHaveValue('> ![alpha](https://image.url)'));

    selectRange(textarea, 0, textarea.value.length);
    clickToolbar('common.markdownEditor.toolbar.quote');
    await waitFor(() => expect(textarea).toHaveValue('![alpha](https://image.url)'));
  });

  it('toggles multiline unordered lists without stacking markers', async () => {
    const { textarea } = setup('alpha\nbeta');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.unorderedList');

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n- beta'));
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.unorderedList');

    await waitFor(() => expect(textarea).toHaveValue('alpha\nbeta'));
  });

  it('toggles multiline ordered lists without stacking markers', async () => {
    const { textarea } = setup('alpha\nbeta');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.orderedList');

    await waitFor(() => expect(textarea).toHaveValue('1. alpha\n2. beta'));
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.orderedList');

    await waitFor(() => expect(textarea).toHaveValue('alpha\nbeta'));
  });

  it('converts unordered lists to ordered lists', async () => {
    const { textarea } = setup('- alpha\n- beta');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.orderedList');

    await waitFor(() => expect(textarea).toHaveValue('1. alpha\n2. beta'));
  });

  it('converts ordered lists to unordered lists', async () => {
    const { textarea } = setup('1. alpha\n2. beta');
    selectRange(textarea, 0, textarea.value.length);

    clickToolbar('common.markdownEditor.toolbar.unorderedList');

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n- beta'));
  });

  it('expands partial-line selections to full lines for list commands', async () => {
    const { textarea } = setup('alpha\nbeta\ngamma');
    selectRange(textarea, 2, 8);

    clickToolbar('common.markdownEditor.toolbar.unorderedList');

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n- beta\ngamma'));
  });

  it('continues and exits unordered lists with Enter', async () => {
    const { textarea } = setup('- alpha');
    selectRange(textarea, textarea.value.length, textarea.value.length);

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', keyCode: 13 });

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n- '));
    selectRange(textarea, textarea.value.length, textarea.value.length);

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', keyCode: 13 });

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n'));
  });

  it('preserves unordered list content after the cursor when pressing Enter after the marker', async () => {
    const { textarea } = setup('- alpha');
    selectRange(textarea, 2, 2);

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', keyCode: 13 });

    await waitFor(() => expect(textarea).toHaveValue('- \n- alpha'));
  });

  it('continues ordered lists with incremented numbering', async () => {
    const { textarea } = setup('1. alpha');
    selectRange(textarea, textarea.value.length, textarea.value.length);

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', keyCode: 13 });

    await waitFor(() => expect(textarea).toHaveValue('1. alpha\n2. '));
  });

  it('preserves ordered list content after the cursor when pressing Enter after the marker', async () => {
    const { textarea } = setup('1. alpha');
    selectRange(textarea, 3, 3);

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', keyCode: 13 });

    await waitFor(() => expect(textarea).toHaveValue('1. \n2. alpha'));
  });

  it('indents and outdents selected list lines with Tab and Shift+Tab', async () => {
    const { textarea } = setup('- alpha\n- beta');
    selectRange(textarea, 0, textarea.value.length);

    fireEvent.keyDown(textarea, { key: 'Tab', code: 'Tab' });

    await waitFor(() => expect(textarea).toHaveValue('  - alpha\n  - beta'));
    selectRange(textarea, 0, textarea.value.length);

    fireEvent.keyDown(textarea, { key: 'Tab', code: 'Tab', shiftKey: true });

    await waitFor(() => expect(textarea).toHaveValue('- alpha\n- beta'));
  });
});

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarkdownSyntaxHighlighter } from './markdownSyntaxHighlighter';

vi.mock('react-syntax-highlighter', () => {
  throw new Error('load failed');
});

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: {},
  oneLight: {},
}));

describe('MarkdownSyntaxHighlighter', () => {
  it('keeps rendering plain code when the highlighter import fails', async () => {
    render(<MarkdownSyntaxHighlighter code="const value = 1;" language="typescript" />);

    await waitFor(() => expect(screen.getByText('const value = 1;')).toBeTruthy());
    expect(screen.queryByTestId('syntax-highlighter')).toBeNull();
  });
});

import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithQuery } from '@/__tests__/utils/render';
import SingleDocumentWorkflow from './SingleDocumentWorkflow';
import type { SingleDocumentSource } from '../../model/singleDocumentSource';

vi.mock('@/shared/hooks/useI18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }));

describe('SingleDocumentWorkflow', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads and shows document content for the default scope', async () => {
    const source: SingleDocumentSource = {
      load: vi.fn().mockResolvedValue({ content: 'AGENTS BODY' }),
      save: vi.fn(),
    };

    renderWithQuery(
      <SingleDocumentWorkflow
        queryKey={['agents-md', 'claude']}
        source={source}
        scopes={['project', 'user']}
        titleKey="ns.title"
        fileName="AGENTS.md"
        i18nNamespace="ns"
      />,
    );

    await waitFor(() => expect(source.load).toHaveBeenCalledWith('project'));
    expect(await screen.findByDisplayValue('AGENTS BODY')).toBeInTheDocument();
  });

  it('renders optional header content after loading', async () => {
    const source: SingleDocumentSource = {
      load: vi.fn().mockResolvedValue({ content: '' }),
      save: vi.fn(),
    };

    renderWithQuery(
      <SingleDocumentWorkflow
        queryKey={['agents-md', 'codex']}
        source={source}
        scopes={['project']}
        titleKey="ns.title"
        fileName="AGENTS.md"
        i18nNamespace="ns"
        renderHeader={() => <div data-testid="caveats">!</div>}
      />,
    );

    expect(await screen.findByTestId('caveats')).toBeInTheDocument();
  });

  it('saves edited content and disables save when unchanged', async () => {
    const source: SingleDocumentSource = {
      load: vi.fn().mockResolvedValue({ content: 'before' }),
      save: vi.fn().mockResolvedValue(undefined),
    };

    renderWithQuery(
      <SingleDocumentWorkflow
        queryKey={['agents-md', 'claude']}
        source={source}
        scopes={['project']}
        titleKey="ns.title"
        fileName="AGENTS.md"
        i18nNamespace="ns"
      />,
    );

    const editor = await screen.findByDisplayValue('before');
    const save = screen.getByRole('button', { name: /ns\.agentsMd\.actions\.save/ });
    expect(save).toBeDisabled();

    fireEvent.change(editor, { target: { value: 'after' } });
    expect(save).not.toBeDisabled();
    fireEvent.click(save);

    await waitFor(() => expect(source.save).toHaveBeenCalledWith('project', 'after'));
  });
});

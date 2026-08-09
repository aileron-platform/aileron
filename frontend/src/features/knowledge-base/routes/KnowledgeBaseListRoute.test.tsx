import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseListRoute } from './KnowledgeBaseListRoute';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    state: { currentLanguage: 'en' },
  }),
}));

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    knowledgeBases: [],
    attachmentCounts: {},
    isLoadingKnowledgeBases: false,
    listError: null,
    reloadKnowledgeBases: vi.fn(),
  }),
}));

vi.mock('../components/KnowledgeBaseCreateDialog', () => ({
  KnowledgeBaseCreateDialog: () => null,
}));

describe('KnowledgeBaseListRoute', () => {
  it('uses the shared empty state when no knowledge base exists', () => {
    render(
      <MemoryRouter>
        <KnowledgeBaseListRoute />
      </MemoryRouter>,
    );

    const title = screen.getByText('knowledgeBase.list.empty');
    expect(title).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'knowledgeBase.list.createAction' }))
      .toHaveLength(2);
  });
});

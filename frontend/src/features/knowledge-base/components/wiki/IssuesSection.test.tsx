import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { IssuesSection } from './IssuesSection';
import { runKnowledgeBaseLint } from '@/features/knowledge-base/api/knowledgeBaseApi';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      const labels: Record<string, string> = {
        'knowledgeBase.wiki.issues.title': 'Issues',
        'knowledgeBase.wiki.issues.lint.title': 'Lint',
        'knowledgeBase.wiki.issues.lint.runButton': 'Run lint',
        'knowledgeBase.wiki.issues.lint.initial': 'Click Run lint',
        'knowledgeBase.wiki.issues.reviews.title': 'Reviews',
        'knowledgeBase.wiki.issues.reviews.empty': 'No open reviews',
        'knowledgeBase.wiki.issues.healthy': 'No issues',
      };
      return params?.defaultValue ? String(params.defaultValue) : labels[key] ?? key;
    },
  }),
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  listKnowledgeBaseReviews: vi.fn(async () => ({
    items: [{ id: 'review-1', type: 'contradiction', pagePath: 'wiki/entities/openai.md', detail: 'Conflict', status: 'open' }],
    counts: { open: 1 },
  })),
  runKnowledgeBaseLint: vi.fn(async () => ({
    kbId: 'kb-1',
    generatedAt: '2026-05-01T00:00:00Z',
    issueCounts: { orphan: 1 },
    issues: [{ issueType: 'orphan', severity: 'warning', path: 'wiki/entities/foo.md', details: {} }],
  })),
  resolveKnowledgeBaseReview: vi.fn(),
  dismissKnowledgeBaseReview: vi.fn(),
  convertKnowledgeBaseReview: vi.fn(),
}));

describe('IssuesSection', () => {
  it('runs lint and selects lint and review items', async () => {
    const user = userEvent.setup();
    const onSelectIssue = vi.fn();

    render(
      <IssuesSection
        kbId="kb-1"
        selectedIssue={null}
        onSelectIssue={onSelectIssue}
        onConverted={vi.fn()}
      />,
    );

    await screen.findByText('Conflict');
    await user.click(screen.getByRole('button', { name: 'Run lint' }));
    await waitFor(() => expect(runKnowledgeBaseLint).toHaveBeenCalledWith('kb-1'));
    await user.click(await screen.findByText('orphan'));
    expect(onSelectIssue).toHaveBeenCalledWith(expect.objectContaining({ kind: 'lint', path: 'wiki/entities/foo.md' }));

    await user.click(screen.getByText('Conflict'));
    expect(onSelectIssue).toHaveBeenCalledWith(expect.objectContaining({ kind: 'review', path: 'wiki/entities/openai.md' }));
  });
});

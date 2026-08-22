import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PromptInvocationPickerDialog } from './PromptInvocationPickerDialog';
import type { PromptInvocationCatalog } from '@/shared/types/promptInvocations';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const degradedCatalog: PromptInvocationCatalog = {
  workspaceId: 'ws-1',
  agenticTool: 'codex',
  completeness: 'degraded',
  revision: 'revision-1',
  availableScopes: ['project', 'user'],
  sourceErrors: [
    {
      source: 'slash-commands',
      errorCode: 'PROMPT_INVOCATION_SOURCE_UNAVAILABLE',
      message: 'commands unavailable',
    },
  ],
  items: [
    {
      id: 'codex:skill:project:review/SKILL.md',
      sourceKey: 'review/SKILL.md',
      fileName: 'SKILL.md',
      kind: 'skill',
      scope: 'project',
      displayName: 'review',
      category: 'project',
      description: 'Review the current changes',
      invocation: '$review',
      tags: [],
    },
  ],
};

describe('PromptInvocationPickerDialog', () => {
  it('keeps degraded Catalog items selectable and shows a warning', async () => {
    const user = userEvent.setup();
    const loadCatalog = vi.fn(async () => degradedCatalog);
    const onSelect = vi.fn();

    render(
      <PromptInvocationPickerDialog
        open
        onOpenChange={vi.fn()}
        catalogKey="ws-1:codex"
        loadCatalog={loadCatalog}
        onSelect={onSelect}
      />,
    );

    await waitFor(() => expect(loadCatalog).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'common.promptInvocation.picker.degraded',
    );

    await user.click(screen.getByRole('button', { name: /\$review/i }));
    expect(onSelect).toHaveBeenCalledWith(degradedCatalog.items[0]);
  });

  it('reloads the Catalog every time the dialog opens', async () => {
    const loadCatalog = vi.fn(async () => degradedCatalog);
    const props = {
      onOpenChange: vi.fn(),
      catalogKey: 'ws-1:codex',
      loadCatalog,
      onSelect: vi.fn(),
    };
    const view = render(<PromptInvocationPickerDialog open={false} {...props} />);

    view.rerender(<PromptInvocationPickerDialog open {...props} />);
    await waitFor(() => expect(loadCatalog).toHaveBeenCalledTimes(1));

    view.rerender(<PromptInvocationPickerDialog open={false} {...props} />);
    view.rerender(<PromptInvocationPickerDialog open {...props} />);
    await waitFor(() => expect(loadCatalog).toHaveBeenCalledTimes(2));
  });

  it('distinguishes a degraded Catalog with no available items from an empty result', async () => {
    render(
      <PromptInvocationPickerDialog
        open
        onOpenChange={vi.fn()}
        catalogKey="ws-1:codex"
        loadCatalog={async () => ({ ...degradedCatalog, items: [] })}
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'common.promptInvocation.picker.degradedEmpty',
    );
  });
});

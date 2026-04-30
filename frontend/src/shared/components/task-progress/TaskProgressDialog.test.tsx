import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { TaskProgressDialog } from './TaskProgressDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'common.taskProgress.title': 'Task progress',
        'common.taskProgress.progress': 'Progress',
        'common.taskProgress.close': 'Close',
        'common.taskProgress.startedAt': 'Started at',
        'common.taskProgress.completedAt': 'Completed at',
        'common.taskProgress.status.failed': 'Failed',
        'common.taskProgress.syncedCount': `Synced ${params?.count} items`,
      };
      return translations[key] ?? key;
    },
  }),
}));

describe('TaskProgressDialog', () => {
  it('renders localized labels and closes completed tasks', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <TaskProgressDialog
        open
        onOpenChange={onOpenChange}
        progress={{
          id: 'task-1',
          status: 'failed',
          progress: 45,
          error: 'Clone failed',
          started_at: '2026-04-30T00:00:00.000Z',
        }}
      />,
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Task progress')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Progress')).toBeInTheDocument();
    expect(screen.getByText('Clone failed')).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'Close' })[0]);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

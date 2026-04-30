import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { TaskProgressCard } from './TaskProgressCard';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'common.taskProgress.title': 'Task progress',
        'common.taskProgress.progress': 'Progress',
        'common.taskProgress.close': 'Close',
        'common.taskProgress.startedAt': 'Started at',
        'common.taskProgress.completedAt': 'Completed at',
        'common.taskProgress.status.completed': 'Completed',
        'common.taskProgress.status.running': 'Running',
        'common.taskProgress.syncedCount': `Synced ${params?.count} items`,
      };
      return translations[key] ?? key;
    },
  }),
}));

describe('TaskProgressCard', () => {
  it('renders localized task progress details and dismiss action', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();

    render(
      <TaskProgressCard
        onDismiss={onDismiss}
        progress={{
          id: 'task-1',
          status: 'completed',
          progress: 100,
          message: 'Done',
          started_at: '2026-04-30T00:00:00.000Z',
          completed_at: '2026-04-30T00:01:00.000Z',
          result: {
            message: 'Clone completed',
            synced_count: 3,
          },
        }}
      />,
    );

    expect(screen.getByText('Task progress: Completed')).toBeInTheDocument();
    expect(screen.getByText('Progress')).toBeInTheDocument();
    expect(screen.getByText('Clone completed')).toBeInTheDocument();
    expect(screen.getByText('Synced 3 items')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSchedulesTab } from './KnowledgeBaseSchedulesTab';

const mocks = vi.hoisted(() => ({
  listJobs: vi.fn(),
  createJob: vi.fn(),
  updateJob: vi.fn(),
  toast: vi.fn(),
  t: vi.fn((key: string, params?: Record<string, string>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.schedules.editor.createTitle': '建立 Wiki Index 排程',
      'knowledgeBase.schedules.editor.updateTitle': 'Wiki Index 排程',
      'knowledgeBase.schedules.editor.createHelper': '選擇要負責執行此知識庫 Wiki Index 排程的工作區。',
      'knowledgeBase.schedules.editor.updateHelper':
        '可以調整 cron 排程，或改選其他符合條件的工作區。若選擇不同工作區並儲存，將會把現有排程移動到該工作區。',
      'knowledgeBase.schedules.editor.workspace': '工作區',
      'knowledgeBase.schedules.editor.workspaceEmpty': '尚未掛載至任何工作區',
      'knowledgeBase.schedules.editor.cron': 'Cron schedule',
      'knowledgeBase.schedules.editor.mountNotice':
        '若要在某個工作區設定 Wiki Index 排程，請先將此知識庫掛載到該工作區，並確認掛載模式為可讀寫。',
      'knowledgeBase.schedules.editor.moveNotice':
        '若選擇不同的工作區並儲存，會將現有的 Wiki Index 排程移動到該工作區；每個知識庫只能保有一個排程。',
      'knowledgeBase.schedules.editor.noEligibleWorkspace':
        '目前沒有可讀寫的工作區掛載。請先把此知識庫以可讀寫模式掛載到目標工作區，再設定 Wiki Index 排程。',
      'knowledgeBase.schedules.actions.create': '建立排程',
      'knowledgeBase.schedules.actions.update': '儲存排程',
      'knowledgeBase.schedules.status.active': '啟用',
      'knowledgeBase.common.actions.refresh': '重新整理',
      'knowledgeBase.common.mode.rw': '可讀寫',
      'knowledgeBase.common.mode.ro': '唯讀',
      'knowledgeBase.schedules.defaultName': `${params?.name ?? ''} Wiki Index`,
      'knowledgeBase.schedules.defaultDescription': `定期維護 ${params?.name ?? ''} 的 Team Wiki index。`,
      'knowledgeBase.schedules.defaultOwner': '目前使用者',
      'knowledgeBase.schedules.defaultPrompt': 'Run knowledge base wiki index.',
      'knowledgeBase.schedules.toasts.createSuccess.title': '排程已建立',
      'knowledgeBase.schedules.toasts.createFailed.title': '建立排程失敗',
      'knowledgeBase.schedules.toasts.createFailed.description': '請稍後再試。',
      'knowledgeBase.schedules.toasts.updateSuccess.title': '排程已更新',
      'knowledgeBase.schedules.toasts.updateFailed.title': '更新排程失敗',
      'knowledgeBase.schedules.toasts.updateFailed.description': '請稍後再試。',
      'knowledgeBase.schedules.toasts.loadFailed.title': '載入排程失敗',
      'knowledgeBase.schedules.toasts.loadFailed.description': '請稍後再試。',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/features/automation/services/automationApi', () => ({
  automationApi: {
    listJobs: mocks.listJobs,
    createJob: mocks.createJob,
    updateJob: mocks.updateJob,
  },
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: {
        id: 'user-1',
        name: 'User One',
      },
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: mocks.t,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

const baseExistingJob = {
  id: 'job-1',
  name: 'KB Wiki Index',
  description: 'Existing description',
  owner: 'User One',
  userId: 'user-1',
  workspaceId: 'ws-rw',
  workspaceName: 'docs ws',
  prompt: 'Run knowledge base wiki index.',
  status: 'active' as const,
  trigger: 'cron' as const,
  schedule: '0 9 * * *',
  tags: ['knowledge-base', 'wiki-index'],
  createdAt: '2026-04-29T00:00:00Z',
  updatedAt: '2026-04-29T00:00:00Z',
  successRate: 0,
  failureRate: 0,
  totalExecutions: 0,
  averageDuration: 0,
  notifications: { email: false, slack: false, webhook: false },
  metadata: {
    jobType: 'knowledge_base.wiki_index',
    knowledgeBaseId: 'kb-1',
  },
};

describe('KnowledgeBaseSchedulesTab', () => {
  beforeEach(() => {
    mocks.listJobs.mockReset();
    mocks.createJob.mockReset();
    mocks.updateJob.mockReset();
    mocks.toast.mockReset();
    mocks.t.mockClear();
    mocks.listJobs.mockResolvedValue([]);
    mocks.createJob.mockResolvedValue(baseExistingJob);
    mocks.updateJob.mockResolvedValue(baseExistingJob);
  });

  it('shows the create editor and creates a job for the selected workspace when none exists', async () => {
    mocks.listJobs.mockResolvedValueOnce([]).mockResolvedValueOnce([baseExistingJob]);

    render(
      <KnowledgeBaseSchedulesTab
        knowledgeBaseId="kb-1"
        knowledgeBaseName="Docs"
        accessRole="editor"
        attachments={[
          {
            id: 'att-1',
            workspaceId: 'ws-rw',
            kbId: 'kb-1',
            mountAlias: 'docs',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-29T00:00:00Z',
          },
          {
            id: 'att-2',
            workspaceId: 'ws-ro',
            kbId: 'kb-1',
            mountAlias: 'docs-readonly',
            mode: 'ro',
            attachedById: 'user-1',
            createdAt: '2026-04-29T00:00:00Z',
          },
        ]}
      />,
    );

    expect(await screen.findByText('建立 Wiki Index 排程')).toBeInTheDocument();
    expect(screen.getByText('選擇要負責執行此知識庫 Wiki Index 排程的工作區。')).toBeInTheDocument();

    const select = screen.getByLabelText('工作區');
    const options = within(select).getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent('docs (可讀寫)');
    expect(options[1]).toHaveTextContent('docs-readonly (唯讀)');
    expect(options[1]).toBeDisabled();
    expect(screen.getByText(
      '若要在某個工作區設定 Wiki Index 排程，請先將此知識庫掛載到該工作區，並確認掛載模式為可讀寫。',
    )).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '建立排程' }));

    await waitFor(() => {
      expect(mocks.createJob).toHaveBeenCalledTimes(1);
    });
    expect(mocks.createJob).toHaveBeenCalledWith(expect.objectContaining({
      workspaceId: 'ws-rw',
      schedule: '0 9 * * *',
      metadata: { jobType: 'knowledge_base.wiki_index', knowledgeBaseId: 'kb-1' },
    }));
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ title: '排程已建立' }));
  });

  it('prefills the editor and updates the existing job when one is found', async () => {
    mocks.listJobs.mockResolvedValueOnce([baseExistingJob, {
      ...baseExistingJob,
      id: 'job-other',
      metadata: { jobType: 'knowledge_base.wiki_index', knowledgeBaseId: 'kb-2' },
    }]).mockResolvedValueOnce([{ ...baseExistingJob, workspaceId: 'ws-rw-2' }]);

    render(
      <KnowledgeBaseSchedulesTab
        knowledgeBaseId="kb-1"
        knowledgeBaseName="Docs"
        accessRole="editor"
        attachments={[
          {
            id: 'att-1',
            workspaceId: 'ws-rw',
            kbId: 'kb-1',
            mountAlias: 'docs',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-29T00:00:00Z',
          },
          {
            id: 'att-3',
            workspaceId: 'ws-rw-2',
            kbId: 'kb-1',
            mountAlias: 'docs-2',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-29T00:00:00Z',
          },
        ]}
      />,
    );

    expect(await screen.findByText('Wiki Index 排程')).toBeInTheDocument();
    await waitFor(() => {
      expect((screen.getByLabelText('工作區') as HTMLSelectElement).value).toBe('ws-rw');
    });
    expect(screen.getByText(
      '若選擇不同的工作區並儲存，會將現有的 Wiki Index 排程移動到該工作區；每個知識庫只能保有一個排程。',
    )).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('工作區'), { target: { value: 'ws-rw-2' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存排程' }));

    await waitFor(() => {
      expect(mocks.updateJob).toHaveBeenCalledTimes(1);
    });
    expect(mocks.updateJob).toHaveBeenCalledWith(expect.objectContaining({
      id: 'job-1',
      workspaceId: 'ws-rw-2',
      schedule: '0 9 * * *',
      metadata: { jobType: 'knowledge_base.wiki_index', knowledgeBaseId: 'kb-1' },
    }));
    expect(mocks.createJob).not.toHaveBeenCalled();
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ title: '排程已更新' }));
  });

  it('disables save and shows guidance when no read/write workspace attachments are available', async () => {
    render(
      <KnowledgeBaseSchedulesTab
        knowledgeBaseId="kb-1"
        knowledgeBaseName="Docs"
        accessRole="editor"
        attachments={[
          {
            id: 'att-2',
            workspaceId: 'ws-ro',
            kbId: 'kb-1',
            mountAlias: 'docs-readonly',
            mode: 'ro',
            attachedById: 'user-1',
            createdAt: '2026-04-29T00:00:00Z',
          },
        ]}
      />,
    );

    expect(await screen.findByText(
      '目前沒有可讀寫的工作區掛載。請先把此知識庫以可讀寫模式掛載到目標工作區，再設定 Wiki Index 排程。',
    )).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '建立排程' })).toBeDisabled();
  });

  it('uses i18n keys for new schedule UI labels', async () => {
    render(
      <KnowledgeBaseSchedulesTab
        knowledgeBaseId="kb-1"
        knowledgeBaseName="Docs"
        accessRole="viewer"
        attachments={[]}
      />,
    );

    await screen.findByText('建立 Wiki Index 排程');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.editor.createTitle');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.editor.createHelper');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.editor.workspace');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.editor.cron');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.editor.noEligibleWorkspace');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.actions.create');
  });
});

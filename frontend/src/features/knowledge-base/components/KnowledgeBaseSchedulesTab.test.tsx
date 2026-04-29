import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSchedulesTab } from './KnowledgeBaseSchedulesTab';

const mocks = vi.hoisted(() => ({
  listJobs: vi.fn(),
  createJob: vi.fn(),
  toast: vi.fn(),
  t: vi.fn((key: string, params?: Record<string, string>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.schedules.title': 'Wiki Index 排程',
      'knowledgeBase.schedules.description': '只可選擇已掛載此知識庫且模式為可讀寫的工作區。',
      'knowledgeBase.schedules.create.title': '新增排程',
      'knowledgeBase.schedules.create.workspace': '工作區',
      'knowledgeBase.schedules.create.cron': 'Cron schedule',
      'knowledgeBase.schedules.actions.create': '建立排程',
      'knowledgeBase.schedules.list.title': '既有排程',
      'knowledgeBase.schedules.list.empty': '尚未建立 Wiki Index 排程。',
      'knowledgeBase.schedules.status.active': '啟用',
      'knowledgeBase.common.actions.refresh': '重新整理',
      'knowledgeBase.common.mode.rw': '可讀寫',
      'knowledgeBase.common.mode.ro': '唯讀',
      'knowledgeBase.schedules.defaultName': `${params?.name ?? ''} Wiki Index`,
      'knowledgeBase.schedules.defaultDescription': `定期維護 ${params?.name ?? ''} 的 Team Wiki index。`,
      'knowledgeBase.schedules.defaultOwner': '目前使用者',
      'knowledgeBase.schedules.defaultPrompt': 'Run knowledge base wiki index.',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/features/automation/services/automationApi', () => ({
  automationApi: {
    listJobs: mocks.listJobs,
    createJob: mocks.createJob,
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

describe('KnowledgeBaseSchedulesTab', () => {
  beforeEach(() => {
    mocks.listJobs.mockReset();
    mocks.createJob.mockReset();
    mocks.toast.mockReset();
    mocks.t.mockClear();
    mocks.listJobs.mockResolvedValue([
      {
        id: 'job-1',
        name: 'KB Wiki Index',
        schedule: '0 9 * * *',
        status: 'active',
        metadata: {
          jobType: 'knowledge_base.wiki_index',
          knowledgeBaseId: 'kb-1',
        },
      },
      {
        id: 'job-2',
        name: 'Other KB',
        schedule: '0 10 * * *',
        status: 'active',
        metadata: {
          jobType: 'knowledge_base.wiki_index',
          knowledgeBaseId: 'kb-2',
        },
      },
    ]);
  });

  it('lists attached workspaces and disables read-only attachments', async () => {
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

    expect(await screen.findByText('Wiki Index 排程')).toBeInTheDocument();
    const select = screen.getByLabelText('工作區');
    const options = within(select).getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent('docs (可讀寫)');
    expect(options[1]).toHaveTextContent('docs-readonly (唯讀)');
    expect(options[1]).toBeDisabled();
    expect(await screen.findByText('KB Wiki Index')).toBeInTheDocument();
    expect(screen.queryByText('Other KB')).not.toBeInTheDocument();
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

    await screen.findByText('Wiki Index 排程');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.title');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.description');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.create.workspace');
    expect(mocks.t).toHaveBeenCalledWith('knowledgeBase.schedules.actions.create');
  });
});

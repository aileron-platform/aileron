import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OpenSpecCustomizationSidebar from './OpenSpecCustomizationSidebar';
import OpenSpecCustomizationFeature from './OpenSpecCustomizationFeature';

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: { value?: string; onChange?: (value?: string) => void }) => (
    <textarea
      data-testid="mock-monaco-editor"
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

const {
  refreshCustomizationMock,
  openCustomizationValidationDialogMock,
  openCustomizationDebugDialogMock,
  getCustomizationFileMock,
  updateCustomizationFileMock,
  forkCustomizationSchemaMock,
  initCustomizationSchemaMock,
  toastMock,
  dispatchMock,
} = vi.hoisted(() => ({
  refreshCustomizationMock: vi.fn(),
  openCustomizationValidationDialogMock: vi.fn(),
  openCustomizationDebugDialogMock: vi.fn(),
  getCustomizationFileMock: vi.fn(),
  updateCustomizationFileMock: vi.fn(),
  forkCustomizationSchemaMock: vi.fn(),
  initCustomizationSchemaMock: vi.fn(),
  toastMock: vi.fn(),
  dispatchMock: vi.fn(),
}));

const customizationState = {
  workspaceId: 'ws-1',
  configPath: '/openspec/config.yaml',
  configPresent: true,
  defaultSchema: 'review-flow',
  builtInSchemas: ['spec-driven'],
  schemas: [
    {
      name: 'review-flow',
      path: '/openspec/schemas/review-flow',
      schemaPath: '/openspec/schemas/review-flow/schema.yaml',
      isDefault: true,
      isInvalid: false,
      templateFiles: [
        { name: 'proposal.md', path: '/openspec/schemas/review-flow/templates/proposal.md' },
      ],
    },
  ],
};

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'workspace.openspec.customization.title': '自定流程',
        'workspace.openspec.customization.subtitle': 'subtitle',
        'workspace.openspec.customization.searchPlaceholder': '搜尋 schema 或檔案',
        'workspace.openspec.customization.actions.forkSchema': 'Fork Schema',
        'workspace.openspec.customization.actions.createSchema': 'Create Schema',
        'workspace.openspec.customization.actions.validate': 'Validate',
        'workspace.openspec.customization.actions.debug': 'Debug',
        'workspace.openspec.customization.actions.refresh': '重新整理',
        'workspace.openspec.customization.dialogs.forkDescription': 'fork desc',
        'workspace.openspec.customization.dialogs.createDescription': 'create desc',
        'workspace.openspec.customization.fields.sourceSchema': '來源 schema',
        'workspace.openspec.customization.fields.destinationSchema': '目標 schema',
        'workspace.openspec.customization.fields.schemaName': 'Schema 名稱',
        'workspace.openspec.customization.fields.schemaDescription': 'Schema 描述',
        'workspace.openspec.customization.fields.defaultSchema': 'Default schema',
        'workspace.openspec.customization.fields.templateCount': 'Template 數量',
        'workspace.openspec.customization.messages.schemaForked': 'Schema 已 fork',
        'workspace.openspec.customization.messages.schemaCreated': 'Schema 已建立',
        'workspace.openspec.customization.messages.saved': '已儲存',
        'workspace.openspec.customization.messages.saveFailed': '儲存失敗',
        'workspace.openspec.customization.messages.loadFailed': '載入失敗',
        'workspace.openspec.customization.messages.genericError': '錯誤',
        'workspace.openspec.customization.validationTitle': 'Validate Your Schema',
        'workspace.openspec.customization.debugTitle': 'Debug Schema Resolution',
        'workspace.openspec.customization.debugResolvedName': 'Resolved schema',
        'workspace.openspec.customization.debugSource': 'Source',
        'workspace.openspec.customization.debugPath': 'Path',
        'workspace.openspec.customization.diagnosticsPlaceholder': 'placeholder',
        'workspace.openspec.customization.selectedStep': '採用',
        'workspace.openspec.customization.defaultBadge': 'Default',
        'workspace.openspec.customization.invalidBadge': 'Invalid',
        'workspace.openspec.customization.loadingFile': '載入中',
        'workspace.openspec.customization.emptyEditor': '空狀態',
        'workspace.openspec.sidebar.expand': '展開',
        'workspace.openspec.sidebar.collapse': '收合',
        'common.save': '儲存',
        'common.cancel': '取消',
      };
      return map[key] ?? key;
    },
  }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      ui: {
        currentTheme: 'light',
      },
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    layout: {
      secondColumnCollapsed: false,
    },
    toggleSecondColumn: vi.fn(),
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
    state: {
      openspec: {
        selectedPath: '/openspec/config.yaml',
      },
    },
    dispatch: dispatchMock,
  }),
}));

vi.mock('../OpenSpecWorkspaceContext', () => ({
  useOpenSpecWorkspace: () => ({
    customization: customizationState,
    customizationValidation: {
      targetPath: '/openspec/config.yaml',
      diagnostics: [{ level: 'info', message: 'ok' }],
    },
    customizationDebug: {
      targetPath: '/openspec/config.yaml',
      resolvedName: 'review-flow',
      source: 'project',
      path: '/openspec/schemas/review-flow',
      resolutionOrder: [
        { order: 1, label: 'selected schema', value: 'review-flow', selected: true },
      ],
    },
    customizationDialog: null,
    isCustomizationLoading: false,
    refreshCustomization: refreshCustomizationMock,
    runCustomizationValidate: vi.fn(),
    runCustomizationDebug: vi.fn(),
    openCustomizationValidationDialog: openCustomizationValidationDialogMock,
    openCustomizationDebugDialog: openCustomizationDebugDialogMock,
    closeCustomizationDialog: vi.fn(),
  }),
}));

vi.mock('../../../components/ChatPanel/openSpecApi', async () => {
  const actual = await vi.importActual('../../../components/ChatPanel/openSpecApi');
  return {
    ...actual,
    openSpecApi: {
      getCustomizationFile: getCustomizationFileMock,
      updateCustomizationFile: updateCustomizationFileMock,
      forkCustomizationSchema: forkCustomizationSchemaMock,
      initCustomizationSchema: initCustomizationSchemaMock,
    },
  };
});

describe('OpenSpecCustomization components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCustomizationFileMock.mockResolvedValue({
      workspaceId: 'ws-1',
      path: '/openspec/config.yaml',
      name: 'config.yaml',
      kind: 'config',
      content: 'schema: review-flow\n',
      editable: true,
      language: 'yaml',
      schemaName: null,
      metadata: {},
    });
    updateCustomizationFileMock.mockResolvedValue({ success: true, message: 'saved' });
    forkCustomizationSchemaMock.mockResolvedValue({ success: true, message: 'forked', path: '/openspec/schemas/rapid' });
    initCustomizationSchemaMock.mockResolvedValue({ success: true, message: 'created', path: '/openspec/schemas/new-flow' });
  });

  it('renders customization tree and triggers toolbar actions', async () => {
    const user = userEvent.setup();
    render(<OpenSpecCustomizationSidebar />);

    expect(screen.getByText('config.yaml')).toBeInTheDocument();
    expect(screen.getByText('review-flow')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Validate' }));
    expect(openCustomizationValidationDialogMock).toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Fork Schema' }));
    await user.type(screen.getByLabelText('目標 schema'), 'rapid');
    await user.click(screen.getByRole('button', { name: 'Fork Schema' }));

    await waitFor(() => {
      expect(forkCustomizationSchemaMock).toHaveBeenCalledWith(
        'http://runtime.test',
        'ws-1',
        expect.objectContaining({ destinationSchema: 'rapid' }),
      );
    });
  });

  it('opens create schema dialog and submits schema creation', async () => {
    const user = userEvent.setup();
    render(<OpenSpecCustomizationSidebar />);

    await user.click(screen.getByRole('button', { name: 'Create Schema' }));
    expect(screen.getAllByText('Create Schema').length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText('Schema 名稱'), 'new-flow');
    await user.type(screen.getByLabelText('Schema 描述'), 'Manual QA workflow');
    await user.click(screen.getAllByRole('button', { name: 'Create Schema' }).at(-1)!);

    await waitFor(() => {
      expect(initCustomizationSchemaMock).toHaveBeenCalledWith(
        'http://runtime.test',
        'ws-1',
        expect.objectContaining({
          name: 'new-flow',
          description: 'Manual QA workflow',
        }),
      );
    });
  });

  it('loads selected customization file into the editor', async () => {
    render(<OpenSpecCustomizationFeature />);

    await waitFor(() => {
      expect(getCustomizationFileMock).toHaveBeenCalledWith(
        'http://runtime.test',
        'ws-1',
        '/openspec/config.yaml',
      );
    });

    const editor = await screen.findByTestId('mock-monaco-editor');
    expect(editor).toHaveValue('schema: review-flow\n');
    fireEvent.change(editor, { target: { value: 'schema: rapid\n' } });
    expect(screen.getByRole('button', { name: '儲存' })).toBeEnabled();
  });
});

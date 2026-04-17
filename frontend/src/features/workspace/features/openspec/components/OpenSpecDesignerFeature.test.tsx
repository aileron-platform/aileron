import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import OpenSpecDesignerFeature from './OpenSpecDesignerFeature';
import OpenSpecDesignerSidebar from './OpenSpecDesignerSidebar';

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
  refreshMock,
  toastMock,
  getSchemaDetailMock,
  updateProjectConfigMock,
  validateSchemaMock,
  setDefaultSchemaMock,
  createTestChangeMock,
  forkSchemaMock,
  initSchemaMock,
  updateSchemaMock,
  toggleSecondColumnMock,
  getOpenSpecDesignerSectionMock,
} = vi.hoisted(() => ({
  refreshMock: vi.fn(),
  toastMock: vi.fn(),
  getSchemaDetailMock: vi.fn(),
  updateProjectConfigMock: vi.fn(),
  validateSchemaMock: vi.fn(),
  setDefaultSchemaMock: vi.fn(),
  createTestChangeMock: vi.fn(),
  forkSchemaMock: vi.fn(),
  initSchemaMock: vi.fn(),
  updateSchemaMock: vi.fn(),
  toggleSecondColumnMock: vi.fn(),
  getOpenSpecDesignerSectionMock: vi.fn(() => 'overview'),
}));

const designerResponse = {
  workspaceId: 'ws-1',
  overview: {
    defaultSchema: 'spec-driven',
    configPresent: true,
    configPath: '/openspec/config.yaml',
    projectSchemaCount: 1,
    projectSchemas: [
      {
        name: 'review-flow',
        source: 'project',
        path: '/openspec/schemas/review-flow',
        description: 'Review flow',
        isDefault: false,
        artifactCount: 4,
      },
    ],
    builtInSchemas: ['spec-driven'],
  },
  projectConfig: {
    path: '/openspec/config.yaml',
    present: true,
    defaultSchema: 'spec-driven',
    context: 'Team context',
    rules: {
      proposal: ['Include rollback plan'],
    },
  },
  projectSchemas: [
    {
      name: 'review-flow',
      source: 'project',
      path: '/openspec/schemas/review-flow',
      description: 'Review flow',
      isDefault: false,
      artifactCount: 4,
    },
  ],
  builtInSchemas: ['spec-driven'],
};

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const dictionary: Record<string, string> = {
        'workspace.openspec.designer.title': 'Workflow Designer',
        'workspace.openspec.designer.subtitle': 'Designer subtitle',
        'workspace.openspec.designer.summaryTitle': 'Customization Summary',
        'workspace.openspec.designer.summaryDescription': 'Summary description',
        'workspace.openspec.designer.noDefaultSchema': 'No default schema',
        'workspace.openspec.designer.present': 'Present',
        'workspace.openspec.designer.missing': 'Missing',
        'workspace.openspec.designer.overviewTitle': 'Workflow Designer Overview',
        'workspace.openspec.designer.overviewDescription': 'Overview description',
        'workspace.openspec.designer.sections.overview': 'Overview',
        'workspace.openspec.designer.sections.projectConfig': 'Project Config',
        'workspace.openspec.designer.sections.schemas': 'Schemas',
        'workspace.openspec.designer.sections.validation': 'Validation',
        'workspace.openspec.designer.sectionDescriptions.overview': 'Overview section',
        'workspace.openspec.designer.sectionDescriptions.projectConfig': 'Config section',
        'workspace.openspec.designer.sectionDescriptions.schemas': 'Schema section',
        'workspace.openspec.designer.sectionDescriptions.validation': 'Validation section',
        'workspace.openspec.designer.projectConfigDescription': 'Config description',
        'workspace.openspec.designer.schemasDescription': 'Schemas description',
        'workspace.openspec.designer.schemaListSummary': 'List 2 available schemas and edit the selected one on the right.',
        'workspace.openspec.designer.validationDescription': 'Validation description',
        'workspace.openspec.designer.fields.defaultSchema': 'Default schema',
        'workspace.openspec.designer.fields.context': 'Project context',
        'workspace.openspec.designer.fields.rules': 'Artifact rules',
        'workspace.openspec.designer.fields.sourceSchema': 'Source schema',
        'workspace.openspec.designer.fields.destinationSchema': 'Destination schema',
        'workspace.openspec.designer.fields.schemaName': 'Schema name',
        'workspace.openspec.designer.fields.schemaDescription': 'Schema description',
        'workspace.openspec.designer.fields.applyTracks': 'Apply tracks',
        'workspace.openspec.designer.fields.testChangeName': 'Test change name',
        'workspace.openspec.designer.actions.saveProjectConfig': 'Save project config',
        'workspace.openspec.designer.actions.forkSchema': 'Fork schema',
        'workspace.openspec.designer.actions.initSchema': 'Create schema',
        'workspace.openspec.designer.actions.saveSchema': 'Save schema',
        'workspace.openspec.designer.actions.validate': 'Validate schema',
        'workspace.openspec.designer.actions.setDefault': 'Set as default',
        'workspace.openspec.designer.actions.createTestChange': 'Create test change',
        'workspace.openspec.designer.actions.expandLayout': 'Expand workflow designer',
        'workspace.openspec.designer.actions.restoreLayout': 'Restore workflow designer layout',
        'workspace.openspec.designer.messages.configSaved': 'Project config saved',
        'workspace.openspec.designer.messages.schemaForked': 'Schema forked',
        'workspace.openspec.designer.messages.schemaCreated': 'Schema created',
        'workspace.openspec.designer.messages.schemaSaved': 'Schema saved',
        'workspace.openspec.designer.messages.validationPassed': 'Validation passed',
        'workspace.openspec.designer.messages.validationFailed': 'Validation failed',
        'workspace.openspec.designer.messages.defaultSet': 'Default schema updated',
        'workspace.openspec.designer.messages.testChangeCreated': 'Test change created',
        'workspace.openspec.designer.errors.loadSchemaTitle': 'Load schema failed',
        'workspace.openspec.designer.errors.generic': 'Generic error',
        'workspace.openspec.designer.schemaEditorTitle': 'Schema editor',
        'workspace.openspec.designer.schemaEditorDescription': 'Schema editor description',
        'workspace.openspec.designer.schemaPathLabel': 'Schema path',
        'workspace.openspec.designer.schemaEditabilityLabel': 'Editability',
        'workspace.openspec.designer.schemaEditable': 'Editable',
        'workspace.openspec.designer.schemaReadOnly': 'Read only',
        'workspace.openspec.designer.yamlEditorHint': 'YAML highlighting enabled',
        'workspace.openspec.designer.selectSchema': 'Select a schema',
        'workspace.openspec.designer.defaultLabel': 'Default',
        'workspace.openspec.designer.noDescription': 'No description',
        'workspace.openspec.designer.validationPass': 'Validation passed',
        'workspace.openspec.designer.validationFail': 'Validation failed',
        'workspace.openspec.sidebar.refresh': 'Refresh',
        'workspace.openspec.sidebar.refreshing': 'Refreshing',
        'workspace.layout.expandSidebar': 'Expand sidebar',
        'workspace.layout.collapseSidebar': 'Collapse sidebar',
      };
      if (key === 'workspace.openspec.designer.metrics.config') {
        return `Config: ${String(params?.state ?? '')}`;
      }
      if (key === 'workspace.openspec.designer.metrics.schemas') {
        return `Schemas: ${String(params?.count ?? '')}`;
      }
      if (key === 'workspace.openspec.designer.metrics.defaultSchema') return 'Default schema';
      if (key === 'workspace.openspec.designer.metrics.projectConfig') return 'Project config';
      if (key === 'workspace.openspec.designer.metrics.projectSchemas') return 'Project schemas';
      if (key === 'workspace.openspec.designer.validationResolution') {
        return `Resolved from ${String(params?.source ?? '')} at ${String(params?.path ?? '')}`;
      }
      return dictionary[key] ?? key;
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
    toggleSecondColumn: toggleSecondColumnMock,
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('../OpenSpecWorkspaceContext', () => ({
  useOpenSpecWorkspace: () => ({
    designer: designerResponse,
    isLoading: false,
    refresh: refreshMock,
  }),
}));

vi.mock('../utils/designerRouting', () => ({
  getOpenSpecDesignerSection: getOpenSpecDesignerSectionMock,
}));

vi.mock('../../../components/ChatPanel/openSpecApi', () => ({
  openSpecApi: {
    getSchemaDetail: getSchemaDetailMock,
    updateProjectConfig: updateProjectConfigMock,
    validateSchema: validateSchemaMock,
    setDefaultSchema: setDefaultSchemaMock,
    createTestChange: createTestChangeMock,
    forkSchema: forkSchemaMock,
    initSchema: initSchemaMock,
    updateSchema: updateSchemaMock,
  },
}));

describe('OpenSpecDesigner components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getOpenSpecDesignerSectionMock.mockReturnValue('overview');
    getSchemaDetailMock.mockResolvedValue({
      name: 'spec-driven',
      source: 'package',
      path: '/package/spec-driven',
      description: 'Default workflow',
      version: 1,
      isDefault: true,
      artifacts: [],
      apply: { requires: ['tasks'], tracks: 'tasks.md' },
      rawSchema: 'name: spec-driven\n',
    });
    updateProjectConfigMock.mockResolvedValue({ success: true, message: 'updated' });
    validateSchemaMock.mockResolvedValue({
      success: true,
      message: 'validated',
      validation: {
        schemaName: 'spec-driven',
        valid: true,
        diagnostics: [{ level: 'info', message: 'Schema is valid' }],
        resolutionSource: 'package',
        resolutionPath: '/package/spec-driven',
      },
    });
    setDefaultSchemaMock.mockResolvedValue({ success: true, message: 'default set' });
    createTestChangeMock.mockResolvedValue({ success: true, message: 'change created' });
    forkSchemaMock.mockResolvedValue({ success: true, message: 'forked', schemaName: 'review-flow' });
    initSchemaMock.mockResolvedValue({ success: true, message: 'created', schemaName: 'new-flow' });
    updateSchemaMock.mockResolvedValue({ success: true, message: 'saved', schemaDetail: null });
  });

  it('renders designer sidebar summary and sections', () => {
    getOpenSpecDesignerSectionMock.mockReturnValue('overview');
    render(<OpenSpecDesignerSidebar />, {
      initialRoute: '/workspaces/openspec/designer/overview',
    });

    expect(screen.getByText('Customization Summary')).toBeInTheDocument();
    expect(screen.getByText('Workflow Designer')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Project Config/i })).toBeInTheDocument();
  });

  it('saves project config from the project config section', async () => {
    const user = userEvent.setup();
    getOpenSpecDesignerSectionMock.mockReturnValue('project-config');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/project-config',
    });

    expect(await screen.findByLabelText('Default schema')).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Default schema'));
    await user.type(screen.getByLabelText('Default schema'), 'review-flow');
    await user.clear(screen.getByLabelText('Project context'));
    await user.type(screen.getByLabelText('Project context'), 'Updated context');
    await user.clear(screen.getByLabelText('Artifact rules'));
    await user.type(screen.getByLabelText('Artifact rules'), 'tasks:{enter}  - Keep tasks small');
    await user.click(screen.getByRole('button', { name: 'Save project config' }));

    await waitFor(() => {
      expect(updateProjectConfigMock).toHaveBeenCalledWith(
        'http://runtime.test',
        'ws-1',
        expect.objectContaining({
          defaultSchema: 'review-flow',
          context: 'Updated context',
          rules: { tasks: ['Keep tasks small'] },
        }),
      );
    });
  });

  it('parses artifact rules with YAML-compatible values', async () => {
    const user = userEvent.setup();
    getOpenSpecDesignerSectionMock.mockReturnValue('project-config');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/project-config',
    });

    await user.clear(screen.getByLabelText('Artifact rules'));
    await user.type(
      screen.getByLabelText('Artifact rules'),
      'proposal:{enter}  - Include rollout plan{enter}tasks: Keep tasks small',
    );
    await user.click(screen.getByRole('button', { name: 'Save project config' }));

    await waitFor(() => {
      expect(updateProjectConfigMock).toHaveBeenCalledWith(
        'http://runtime.test',
        'ws-1',
        expect.objectContaining({
          rules: {
            proposal: ['Include rollout plan'],
            tasks: ['Keep tasks small'],
          },
        }),
      );
    });
  });

  it('runs validation and renders diagnostics', async () => {
    const user = userEvent.setup();
    getOpenSpecDesignerSectionMock.mockReturnValue('validation');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/validation',
    });

    expect(await screen.findByRole('button', { name: 'Validate schema' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Validate schema' }));

    await waitFor(() => {
      expect(validateSchemaMock).toHaveBeenCalledWith('http://runtime.test', 'ws-1', 'spec-driven');
    });
    expect(await screen.findByText('Schema is valid')).toBeInTheDocument();
  });

  it('uses known schema options for validation actions', async () => {
    getOpenSpecDesignerSectionMock.mockReturnValue('validation');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/validation',
    });

    expect(await screen.findByRole('button', { name: 'Validate schema' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Set as default' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Create test change' })).toBeDisabled();
    expect(screen.getByText('spec-driven')).toBeInTheDocument();
  });

  it('renders schema management with monaco yaml editor and source selector', async () => {
    const user = userEvent.setup();
    getOpenSpecDesignerSectionMock.mockReturnValue('schemas');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/schemas',
    });

    expect(await screen.findByLabelText('Schema name')).toBeInTheDocument();
    expect(screen.getByTestId('mock-monaco-editor')).toHaveValue('name: spec-driven\n');
    expect(screen.getByText('Editability:')).toBeInTheDocument();
    expect(screen.getByText('YAML highlighting enabled')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Fork schema' }));
    expect(await screen.findByLabelText('Source schema')).toBeInTheDocument();
  });

  it('toggles workflow designer fullscreen from the header action', async () => {
    const user = userEvent.setup();
    getOpenSpecDesignerSectionMock.mockReturnValue('overview');
    render(<OpenSpecDesignerFeature />, {
      initialRoute: '/workspaces/openspec/designer/overview',
    });

    const feature = screen.getByTestId('openspec-designer-feature');
    expect(feature.className).not.toContain('fixed');

    await user.click(screen.getByRole('button', { name: 'Expand workflow designer' }));
    expect(feature.className).toContain('fixed');
    expect(feature.className).toContain('inset-0');
    expect(feature.className).toContain('z-50');

    await user.click(screen.getByRole('button', { name: 'Restore workflow designer layout' }));
    expect(feature.className).not.toContain('fixed');
  });
});

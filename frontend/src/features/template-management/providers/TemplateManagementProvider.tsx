/**
 * TemplateManagementProvider - 範本管理模組狀態提供者
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from 'react';
import type {
  Template,
  TemplateCategory,
  TemplateInstallOptions,
  TemplateStatus,
  TemplateWorkspaceTarget,
} from '@/shared/types/templates';
import { listEnabledTemplateFeatures } from '@/shared/types/templates';

import { createLogger } from '@/shared/services/logger';
import { dispatchWorkspaceTemplateInstalledEvent } from '@/features/workspace/events/templateInstallEvents';

const logger = createLogger('TemplateManagementProvider');
import * as templateApi from '@/features/template-management/api/templateApi';
import { apiClient } from '@/shared/api/apiClient';

export interface TemplateUpsertPayload {
  templateId: string; // 模板代號
  name: string; // 模板名稱
  description?: string;
  version: string;
  author: Template['author'];
  keywords: string[];
  categoryId?: string;
  documentation?: string;
  agentsMd?: string;
  initCommands?: string;
  mcpServers: Template['mcpServers'];
  commands: Template['commands'];
  hooks: Template['hooks'];
  agents: Template['agents'];
  outputStyle: Template['outputStyle'];
  skills: Template['skills'];
  scripts: Template['scripts'];
  isActive?: boolean;
}

interface TemplateManagementState {
  templates: Template[];
  categories: TemplateCategory[];
  workspaces: TemplateWorkspaceTarget[];
  isLoading: boolean;
  error: string | null;
  // layout state 
  layout: {
    // Template Detail 
    detailLeftOpen: boolean;
    detailLeftWidth: number;
    // Template Center 
    centerLeftWidth: number;
    // Columns (tri layout) 
    triPrimaryOpen: boolean;
    triPrimaryWidth: number;
    triSecondaryOpen: boolean;
    triSecondaryWidth: number;
  };
}

const initialState: TemplateManagementState = {
  templates: [],
  categories: [],
  workspaces: [],
  isLoading: true,
  error: null,
  layout: {
    detailLeftOpen: true,
    detailLeftWidth: 256,
    centerLeftWidth: 288,
    triPrimaryOpen: true,
    triPrimaryWidth: 320,
    triSecondaryOpen: true,
    triSecondaryWidth: 360,
  },
};

const actionTypes = {
  INITIALIZE: 'INITIALIZE',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  UPSERT_TEMPLATE: 'UPSERT_TEMPLATE',
  DELETE_TEMPLATE: 'DELETE_TEMPLATE',
  SET_TEMPLATES: 'SET_TEMPLATES',
  SET_LAYOUT: 'SET_LAYOUT',
} as const;

interface BaseAction<T extends string, P = undefined> {
  type: T;
  payload: P;
}

type TemplateManagementAction =
  | BaseAction<typeof actionTypes.INITIALIZE, TemplateManagementState>
  | BaseAction<typeof actionTypes.SET_LOADING, boolean>
  | BaseAction<typeof actionTypes.SET_ERROR, string | null>
  | BaseAction<typeof actionTypes.UPSERT_TEMPLATE, Template>
  | BaseAction<typeof actionTypes.DELETE_TEMPLATE, string>
  | BaseAction<typeof actionTypes.SET_TEMPLATES, Template[]>
  | BaseAction<typeof actionTypes.SET_LAYOUT, Partial<TemplateManagementState['layout']>>;

const templateManagementReducer = (
  state: TemplateManagementState,
  action: TemplateManagementAction,
): TemplateManagementState => {
  switch (action.type) {
    case actionTypes.INITIALIZE:
      return {
        ...state,
        templates: action.payload.templates,
        categories: action.payload.categories,
        workspaces: action.payload.workspaces,
        isLoading: false,
        error: null,
        layout: state.layout,
      };
    case actionTypes.SET_LOADING:
      return {
        ...state,
        isLoading: action.payload,
      };
    case actionTypes.SET_ERROR:
      return {
        ...state,
        error: action.payload,
      };
    case actionTypes.UPSERT_TEMPLATE: {
      const exists = state.templates.some(item => item.id === action.payload.id);
      const templates = exists
        ? state.templates.map(item => (item.id === action.payload.id ? action.payload : item))
        : [action.payload, ...state.templates];
      return {
        ...state,
        templates,
      };
    }
    case actionTypes.DELETE_TEMPLATE:
      return {
        ...state,
        templates: state.templates.filter(item => item.id !== action.payload),
      };
    case actionTypes.SET_TEMPLATES:
      return {
        ...state,
        templates: action.payload,
      };
    case actionTypes.SET_LAYOUT:
      return {
        ...state,
        layout: { ...state.layout, ...action.payload },
      };
    default:
      return state;
  }
};

export interface TemplateManagementContextValue {
  templates: Template[];
  categories: TemplateCategory[];
  workspaces: TemplateWorkspaceTarget[];
  isLoading: boolean;
  error: string | null;
  getTemplateById: (id: string) => Template | undefined;
  createTemplate: (payload: TemplateUpsertPayload) => Promise<Template>;
  updateTemplate: (id: string, payload: TemplateUpsertPayload) => Promise<Template>;
  deleteTemplate: (id: string) => Promise<void>;
  importTemplate: (file: File) => Promise<void>;
  exportTemplate: (id: string) => Promise<void>;
  installTemplate: (
    templateId: string,
    workspaceId: string,
    options: TemplateInstallOptions,
  ) => Promise<{ template: Template; workspace: TemplateWorkspaceTarget; options: TemplateInstallOptions }>;
  reloadFromSource: () => Promise<void>;
  // layout
  layout: TemplateManagementState['layout'];
  setDetailLeftOpen: (open: boolean) => void;
  setDetailLeftWidth: (w: number) => void;
  setCenterLeftWidth: (w: number) => void;
  setTriPrimaryOpen: (open: boolean) => void;
  setTriPrimaryWidth: (w: number) => void;
  setTriSecondaryOpen: (open: boolean) => void;
  setTriSecondaryWidth: (w: number) => void;
}

const TemplateManagementContext = createContext<TemplateManagementContextValue | undefined>(undefined);

export interface TemplateManagementProviderProps {
  children: React.ReactNode;
}

const buildTemplateFromPayload = (
  payload: TemplateUpsertPayload,
  categories: TemplateCategory[],
): Template => {
  const matchedCategory = payload.categoryId
    ? categories.find(item => item.id === payload.categoryId)
    : undefined;

  return {
    id: payload.templateId, // 使用 templateId 作為 id
    name: payload.name,
    description: payload.description,
    author: payload.author,
    keywords: payload.keywords,
    version: payload.version,
    status: payload.isActive === false ? 'draft' : 'released',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    documentation: payload.documentation,
    agentsMd: payload.agentsMd,
    initCommands: payload.initCommands,
    isActive: payload.isActive ?? true,
    mcpServers: payload.mcpServers,
    commands: payload.commands,
    hooks: payload.hooks,
    agents: payload.agents,
    outputStyle: payload.outputStyle,
    scripts: payload.scripts,
    skills: payload.skills,
    categoryId: payload.categoryId,
    categoryName: matchedCategory?.name,
  };
};

export const TemplateManagementProvider: React.FC<TemplateManagementProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(templateManagementReducer, initialState);

  const initialize = useCallback(async () => {
    dispatch({ type: actionTypes.SET_LOADING, payload: true });
    try {
      // 先獲取 categories 和 templates，以便正確映射 categoryName
      const [templatesResponse, categoriesResponse, workspacesResponse] = await Promise.all([
        templateApi.listTemplates({
          page: 1,
          limit: 100
        }),
        apiClient.get<{
          items: Array<{
            id: string;
            name: string;
            description?: string;
            icon?: string;
            sortOrder?: number;
            isActive?: boolean;
          }>;
        }>('/templates/categories'),
        apiClient.get<{
          items: Array<{
            id: string;
            name: string;
            description?: string;
            cliType?: string;
            updatedAt: string;
          }>;
        }>('/workspaces/?page=1&pageSize=100'),
      ]);

      // 將 categories API 回應轉換為 TemplateCategory 格式
      const categories: TemplateCategory[] = (categoriesResponse.items || []).map(cat => ({
        id: cat.id,
        name: cat.name,
        description: cat.description,
        icon: cat.icon,
        sortOrder: cat.sortOrder ?? 0,
        isActive: cat.isActive ?? true,
      }));

      // 轉換 API 響應到前端格式
      const templates: Template[] = templatesResponse.items.map(apiTemplate => {
        // 根據 categoryId 查找分類名稱
        const matchedCategory = categories.find(cat => cat.id === apiTemplate.categoryId);

        return {
          id: apiTemplate.id,
          name: apiTemplate.name,
          description: apiTemplate.description,
          author: apiTemplate.author,
          keywords: apiTemplate.keywords ?? [],
          version: apiTemplate.version,
          status: apiTemplate.status as TemplateStatus,
          createdAt: apiTemplate.created_at,
          updatedAt: apiTemplate.updated_at,
          isActive: apiTemplate.status === 'released',
          cliType: apiTemplate.cli_type as any,
          documentation: apiTemplate.documentation,
          agentsMd: apiTemplate.agentsMd,
          initCommands: apiTemplate.initCommands,
          // 使用後端返回的配置數據，如果為空則設為空陣列
          mcpServers: apiTemplate.mcpServers || [],
          commands: apiTemplate.commands || [],
          hooks: apiTemplate.hooks || [],
          agents: apiTemplate.agents || [],
          outputStyle: apiTemplate.outputStyle || [],
          skills: apiTemplate.skills || [],
          scripts: apiTemplate.scripts || [],
          categoryId: apiTemplate.categoryId,
          categoryName: matchedCategory?.name,
        };
      });

      // 將 workspace API 回應轉換為 TemplateWorkspaceTarget 格式
      const workspaces: TemplateWorkspaceTarget[] = (workspacesResponse.items || []).map(ws => ({
        id: ws.id,
        name: ws.name,
        description: ws.description,
        cliType: ws.cliType as any,
        updatedAt: ws.updatedAt,
      }));

      dispatch({
        type: actionTypes.INITIALIZE,
        payload: {
          templates,
          categories,
          workspaces,
          isLoading: false,
          error: null,
          layout: state.layout,
        },
      });
    } catch (error) {
      dispatch({ type: actionTypes.SET_ERROR, payload: 'Failed to load template data' });
      dispatch({ type: actionTypes.SET_LOADING, payload: false });
      logger.error('初始化失敗', { error });
    }
  }, []);

  useEffect(() => {
    initialize();
  }, [initialize]);

  const getTemplateById = useCallback(
    (id: string): Template | undefined => state.templates.find(item => item.id === id),
    [state.templates],
  );

  const createTemplate = useCallback(
    async (payload: TemplateUpsertPayload): Promise<Template> => {
      const template = buildTemplateFromPayload(payload, state.categories);
      dispatch({ type: actionTypes.UPSERT_TEMPLATE, payload: template });
      return template;
    },
    [state.categories],
  );

  const updateTemplate = useCallback(
    async (id: string, payload: TemplateUpsertPayload): Promise<Template> => {
      const existing = getTemplateById(id);
      const template = buildTemplateFromPayload(payload, state.categories);
      dispatch({ type: actionTypes.UPSERT_TEMPLATE, payload: template });
      return {
        ...template,
        createdAt: existing?.createdAt ?? template.createdAt,
      };
    },
    [getTemplateById, state.categories],
  );

  const deleteTemplate = useCallback(async (id: string): Promise<void> => {
    try {
      // 調用後端 API 刪除模板
      await templateApi.deleteTemplate(id);
      // 成功後從前端狀態中移除
      dispatch({ type: actionTypes.DELETE_TEMPLATE, payload: id });
    } catch (error) {
      logger.error('刪除模板失敗', { error });
      throw error; // 讓上層處理錯誤
    }
  }, []);

  const importTemplate = useCallback(async (file: File): Promise<void> => {
    try {
      await templateApi.importTemplate(file);
      // 匯入成功後重新載入模板列表
      await initialize();
    } catch (error) {
      logger.error('匯入模板失敗', { error });
      throw error;
    }
  }, [initialize]);

  const exportTemplate = useCallback(async (id: string): Promise<void> => {
    try {
      const template = getTemplateById(id);
      const blob = await templateApi.exportTemplate(id, template?.cliType);

      // 建立下載連結
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${id}.zip`;
      document.body.appendChild(a);
      a.click();

      // 清理
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      logger.error('匯出模板失敗', { error });
      throw error;
    }
  }, [getTemplateById]);

  const installTemplate = useCallback(
    async (
      templateId: string,
      workspaceId: string,
      options: TemplateInstallOptions,
    ): Promise<{ template: Template; workspace: TemplateWorkspaceTarget; options: TemplateInstallOptions }> => {
      const template = getTemplateById(templateId);
      const workspace = state.workspaces.find(item => item.id === workspaceId);
      if (!template) {
        throw new Error('Template not found');
      }
      if (!workspace) {
        throw new Error('Workspace not found');
      }

      // 調用後端 API 執行實際安裝
      await templateApi.installTemplate(templateId, workspaceId);

      dispatchWorkspaceTemplateInstalledEvent({
        workspaceId,
        templateId,
        installedFeatures: listEnabledTemplateFeatures(options),
      });

      return { template, workspace, options };
    },
    [getTemplateById, state.workspaces],
  );

  const reloadFromSource = useCallback(async () => {
    // 重新從後端載入資料
    await initialize();
  }, [initialize]);
  // layout setters
  const setDetailLeftOpen = useCallback((open: boolean) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { detailLeftOpen: open } });
  }, []);
  const setDetailLeftWidth = useCallback((w: number) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { detailLeftWidth: w } });
  }, []);
  const setCenterLeftWidth = useCallback((w: number) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { centerLeftWidth: w } });
  }, []);
  const setTriPrimaryOpen = useCallback((open: boolean) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { triPrimaryOpen: open } });
  }, []);
  const setTriPrimaryWidth = useCallback((w: number) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { triPrimaryWidth: w } });
  }, []);
  const setTriSecondaryOpen = useCallback((open: boolean) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { triSecondaryOpen: open } });
  }, []);
  const setTriSecondaryWidth = useCallback((w: number) => {
    dispatch({ type: actionTypes.SET_LAYOUT, payload: { triSecondaryWidth: w } });
  }, []);


  const value = useMemo<TemplateManagementContextValue>(() => ({
    templates: state.templates,
    categories: state.categories,
    workspaces: state.workspaces,
    isLoading: state.isLoading,
    error: state.error,
    getTemplateById,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    importTemplate,
    exportTemplate,
    installTemplate,
    reloadFromSource,
    // layout
    layout: state.layout,
    setDetailLeftOpen,
    setDetailLeftWidth,
    setCenterLeftWidth,
    setTriPrimaryOpen,
    setTriPrimaryWidth,
    setTriSecondaryOpen,
    setTriSecondaryWidth,
  }), [
    state.templates,
    state.categories,
    state.workspaces,
    state.isLoading,
    state.error,
    state.layout,
    getTemplateById,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    importTemplate,
    exportTemplate,
    installTemplate,
    reloadFromSource,
    setDetailLeftOpen,
    setDetailLeftWidth,
    setCenterLeftWidth,
    setTriPrimaryOpen,
    setTriPrimaryWidth,
    setTriSecondaryOpen,
    setTriSecondaryWidth,
  ]);

  return (
    <TemplateManagementContext.Provider value={value}>
      {children}
    </TemplateManagementContext.Provider>
  );
};

export const useTemplateManagementContext = (): TemplateManagementContextValue => {
  const context = useContext(TemplateManagementContext);
  if (!context) {
    throw new Error('useTemplateManagementContext 必須在 TemplateManagementProvider 內使用');
  }
  return context;
};

export default TemplateManagementProvider;

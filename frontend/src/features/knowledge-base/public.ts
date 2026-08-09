export type {
  KnowledgeBaseSummary,
  KnowledgeBaseWorkspaceUsageResponse,
} from './model/knowledgeBaseTypes';

export const loadKnowledgeBaseModule = () =>
  import('./KnowledgeBaseModule').then(({ KnowledgeBaseModule }) => ({
    default: KnowledgeBaseModule,
  }));

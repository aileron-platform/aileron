import type { AgentScope } from './model/documents';
import {
  getDocumentActionPolicy,
  getWritableDocumentScopes,
  isReadOnlyDocumentScope,
  type DocumentActionPolicy,
} from '@/shared/components/document-resource';

export type AgentSettingsScopeSelection = AgentScope | 'all';
export type CodexFileScope = Extract<AgentScope, 'project' | 'user' | 'plugin'>;

export type AgentDocumentActionPolicy = DocumentActionPolicy;

export const isReadOnlyAgentScope = isReadOnlyDocumentScope;

export const getWritableAgentScopes = getWritableDocumentScopes;

export const resolveAgentSettingsSelectedScope = (
  selectedScope: AgentSettingsScopeSelection,
  effectiveScopes: AgentScope[],
): AgentSettingsScopeSelection => (
  selectedScope !== 'all' && !effectiveScopes.includes(selectedScope) ? 'all' : selectedScope
);

export const toCodexFileScope = (scope: AgentScope): CodexFileScope => {
  if (scope === 'plugin') return 'plugin';
  if (scope === 'user') return 'user';
  return 'project';
};

export const getAgentDocumentActionPolicy = (
  document: { scope: AgentScope } | null | undefined,
): AgentDocumentActionPolicy => getDocumentActionPolicy(document);

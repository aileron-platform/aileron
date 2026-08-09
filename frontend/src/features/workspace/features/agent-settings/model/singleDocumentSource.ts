import type { AgentScope } from './documents';

export interface SingleDocumentLoadResult {
  content: string;
  metadata?: Record<string, unknown>;
}

export interface SingleDocumentSource {
  load(scope: AgentScope): Promise<SingleDocumentLoadResult>;
  save(scope: AgentScope, content: string): Promise<void>;
}

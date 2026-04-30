export interface TemplateMetadataItem {
  id: string;
  fileName: string;
  description?: string;
  content: string;
}

export type CommandData = TemplateMetadataItem;

export type AgentData = TemplateMetadataItem;

export type OutputStyleData = TemplateMetadataItem;

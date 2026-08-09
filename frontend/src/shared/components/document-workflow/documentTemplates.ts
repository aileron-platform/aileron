import { basenameWithoutKnownDocumentExtension, type DocumentMetadataValue } from './documentMetadata';

export type DocumentTemplateResourceType = 'slashCommand' | 'subagent' | 'outputStyle';
export type DocumentTemplateContentFormat = 'markdown' | 'toml' | 'plain';
export type TemplateTranslator = (key: string, values?: Record<string, unknown>) => string;

export const createDocumentTemplate = (
  resourceType: DocumentTemplateResourceType,
  metadata: DocumentMetadataValue,
  t: TemplateTranslator,
  contentFormat: DocumentTemplateContentFormat = 'markdown',
): string => {
  const name = basenameWithoutKnownDocumentExtension(metadata.fileName || 'document');
  if (resourceType === 'subagent') {
    const description = t('shared.documentWorkflow.templates.subagent.description', { name });
    const developerInstructions = t('shared.documentWorkflow.templates.subagent.developerInstructions', { name });
    if (contentFormat === 'toml') {
      return [
        `name = "${name}"`,
        `description = "${description}"`,
        `developer_instructions = "${developerInstructions}"`,
        '',
      ].join('\n');
    }
    return [
      '---',
      `name: ${name}`,
      `description: ${description}`,
      '---',
      '',
      `# ${name}`,
      '',
    ].join('\n');
  }
  if (resourceType === 'outputStyle') {
    return [
      `# ${t('shared.documentWorkflow.templates.outputStyle.title')}`,
      '',
    ].join('\n');
  }
  return [`# ${name}`, ''].join('\n');
};

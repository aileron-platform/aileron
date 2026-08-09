import {
  replaceFileNameInPath,
  splitDocumentPath,
  type DocumentMetadataAdapter,
  type DocumentMetadataValue,
} from '@/shared/components/document-workflow';
import type { DocumentResourceItem, DocumentResourceScope } from './model/documentResourceTypes';

export type DocumentResourceType = 'slashCommand' | 'subagent' | 'outputStyle';

const metadataPathOf = (document: DocumentResourceItem | null): string => {
  if (!document) return '';
  return (document.metadata?.relativePath as string | undefined)
    ?? (document.metadata?.fileName as string | undefined)
    ?? document.title;
};

const idFor = (scope: string | undefined, fileName: string): string => `${scope ?? 'project'}:${fileName}`;

export const createDocumentMetadataAdapter = (
  resourceType: DocumentResourceType,
  options: { scope?: boolean } = {},
): DocumentMetadataAdapter<DocumentResourceItem> => {
  const scopeEnabled = options.scope ?? true;
  const supportsNamespace = resourceType === 'slashCommand';
  const documentIdFor = (scope: string | undefined, fileName: string): string =>
    scopeEnabled ? idFor(scope, fileName) : fileName;
  return {
    capabilities: {
      scope: scopeEnabled,
      namespace: supportsNamespace,
    },
    read(document) {
      const path = metadataPathOf(document);
      const split = splitDocumentPath(path);
      return {
        fileName: split.fileName,
        namespace: supportsNamespace ? split.namespace : undefined,
        path: path || undefined,
        scope: scopeEnabled ? (document?.scope ?? 'project') : undefined,
      };
    },
    buildCreate(input: DocumentMetadataValue, templateContent: string): DocumentResourceItem {
      const scope = (input.scope as DocumentResourceScope | undefined) ?? 'project';
      const fileName = supportsNamespace && input.namespace
        ? `${input.namespace}/${input.fileName}`
        : (input.path ?? input.fileName);
      return {
        id: documentIdFor(scope, fileName),
        title: input.fileName,
        description: '',
        scope,
        content: templateContent,
        metadata: {
          fileName,
        },
      };
    },
    applyRename(document, fileName) {
      const previousFileName = metadataPathOf(document);
      const displayFileName = splitDocumentPath(fileName).fileName;
      const nextFileName = supportsNamespace
        ? (splitDocumentPath(fileName).namespace ? fileName : replaceFileNameInPath(previousFileName, fileName))
        : fileName;
      return {
        ...document,
        id: documentIdFor(document.scope, nextFileName),
        title: displayFileName,
        metadata: {
          ...document.metadata,
          fileName: nextFileName,
          previousFileName: resourceType === 'subagent' || !scopeEnabled
            ? previousFileName
            : document.metadata?.previousFileName,
        },
      };
    },
  };
};

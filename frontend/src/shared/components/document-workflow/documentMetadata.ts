import { stripKnownDocumentExtension } from './documentExtensions';

export interface DocumentMetadataValue {
  fileName: string;
  scope?: string;
  namespace?: string;
  path?: string;
}

export interface DocumentMetadataCapabilities {
  scope: boolean;
  namespace: boolean;
}

export interface DocumentMetadataAdapter<TDocument> {
  capabilities: DocumentMetadataCapabilities;
  read(document: TDocument | null): DocumentMetadataValue;
  buildCreate(input: DocumentMetadataValue, templateContent: string): TDocument;
  applyRename(document: TDocument, fileName: string): TDocument;
}

export const splitDocumentPath = (path: string): DocumentMetadataValue => {
  const normalized = path.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  const segments = normalized.split('/').filter(Boolean);
  const fileName = segments.at(-1) ?? '';
  const namespace = segments.length > 1 ? segments.slice(0, -1).join('/') : undefined;
  return { fileName, namespace, path: normalized };
};

export const replaceFileNameInPath = (path: string, fileName: string): string => {
  const current = splitDocumentPath(path);
  return current.namespace ? `${current.namespace}/${fileName}` : fileName;
};

export const basenameWithoutKnownDocumentExtension = (pathOrFileName: string): string => {
  const { fileName } = splitDocumentPath(pathOrFileName);
  return stripKnownDocumentExtension(fileName);
};

import {
  replaceFileNameInPath,
  splitDocumentPath,
  type DocumentMetadataValue,
} from './documentMetadata';
import { stripKnownDocumentExtension } from './documentExtensions';
import type { DocumentTemplateContentFormat, DocumentTemplateResourceType } from './documentTemplates';

export type DocumentResourceProfile = DocumentTemplateResourceType;

const getCanonicalPathSegments = (pathOrFileName: string): string[] => (
  pathOrFileName
    .split('/')
    .map((segment) => segment.trim())
    .filter(Boolean)
);

const getPathBasename = (pathOrFileName: string): string => {
  const canonicalPath = getCanonicalPathSegments(pathOrFileName).join('/');
  return splitDocumentPath(canonicalPath).fileName;
};

export const resolveDocumentExtension = (
  profile: DocumentResourceProfile,
  contentFormat: DocumentTemplateContentFormat,
): '.md' | '.toml' => {
  if (profile === 'subagent' && contentFormat === 'toml') {
    return '.toml';
  }
  return '.md';
};

export const normalizeDocumentFileName = (
  pathOrFileName: string,
  profile: DocumentResourceProfile,
  contentFormat: DocumentTemplateContentFormat,
): string => {
  const trimmed = pathOrFileName.trim();
  if (!trimmed || trimmed.endsWith('/')) {
    return '';
  }
  const canonicalPath = getCanonicalPathSegments(trimmed).join('/');
  const documentPath = splitDocumentPath(canonicalPath);
  const basename = documentPath.fileName;
  const basenameWithoutKnownExtension = stripKnownDocumentExtension(basename);
  if (!basenameWithoutKnownExtension) {
    return '';
  }
  const extension = resolveDocumentExtension(profile, contentFormat);
  return replaceFileNameInPath(canonicalPath, `${basenameWithoutKnownExtension}${extension}`);
};

export const normalizeDocumentMetadata = (
  value: DocumentMetadataValue,
  profile: DocumentResourceProfile,
  contentFormat: DocumentTemplateContentFormat,
): DocumentMetadataValue => {
  const normalizedFileNamePath = normalizeDocumentFileName(value.fileName, profile, contentFormat);
  const fileName = getPathBasename(normalizedFileNamePath);
  const basePath = value.path ?? normalizedFileNamePath;
  const path = basePath
    ? (fileName ? replaceFileNameInPath(basePath, fileName) : '')
    : basePath;
  return {
    ...value,
    fileName,
    ...(path !== undefined ? { path } : {}),
  };
};

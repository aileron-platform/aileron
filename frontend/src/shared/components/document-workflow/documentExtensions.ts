export const KNOWN_DOCUMENT_EXTENSION_PATTERN = /\.(md|markdown|toml)$/i;

export const stripKnownDocumentExtension = (fileName: string): string => (
  fileName.replace(KNOWN_DOCUMENT_EXTENSION_PATTERN, '')
);

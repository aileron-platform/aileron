import type { DocumentResourceScope } from './model/documentResourceTypes';

export interface DocumentActionPolicy {
  canEdit: boolean;
  canDelete: boolean;
  canCopy: boolean;
  canDownload: boolean;
  readOnly: boolean;
}

const READ_ONLY_DOCUMENT_SCOPES = new Set<DocumentResourceScope>(['plugin']);

export const isReadOnlyDocumentScope = (scope: DocumentResourceScope): boolean => READ_ONLY_DOCUMENT_SCOPES.has(scope);

export const getWritableDocumentScopes = (scopes: DocumentResourceScope[]): DocumentResourceScope[] => (
  scopes.filter((scope) => !isReadOnlyDocumentScope(scope))
);

export const getDocumentActionPolicy = (
  document: { scope: DocumentResourceScope } | null | undefined,
): DocumentActionPolicy => {
  const readOnly = document ? isReadOnlyDocumentScope(document.scope) : true;

  return {
    canEdit: Boolean(document && !readOnly),
    canDelete: Boolean(document && !readOnly),
    canCopy: Boolean(document),
    canDownload: Boolean(document),
    readOnly,
  };
};

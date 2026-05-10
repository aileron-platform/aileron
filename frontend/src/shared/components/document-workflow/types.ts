export interface MultiDocumentPersistenceAdapter<TItem> {
  items: TItem[];
  isDirty: (item: TItem) => boolean;
  commit?: (item: TItem) => Promise<void> | void;
  commitAll?: () => Promise<void> | void;
  discard?: () => Promise<void> | void;
  delete?: (item: TItem) => Promise<void> | void;
}

export interface DocumentWorkflowDialogProps<TDocument> {
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: TDocument | null;
  onClose: () => void;
  onSubmit: (document: TDocument) => Promise<void> | void;
}

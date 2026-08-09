import type { createKnowledgeBaseRemoteCapability } from '@/shared/version-control/versionControlRemoteCapability';
import type { VersionControlOperationStatus } from '@/shared/version-control';
import type { VersionControlWorkbenchController } from './useVersionControlWorkbenchController';
import type { VersionControlLfsDialogProps } from './VersionControlLfsDialog';

type RemoteLfsCapability = Pick<
  ReturnType<typeof createKnowledgeBaseRemoteCapability>,
  | 'useLfsPatternsQuery'
  | 'useUpdateLfsPatternsMutation'
  | 'usePreviewLfsSnapshotMutation'
  | 'useConvertLfsSnapshotMutation'
  | 'useCancelOperationMutation'
>;

interface UseVersionControlLfsDialogBindingOptions {
  remote: RemoteLfsCapability;
  controller: VersionControlWorkbenchController;
  requestIdentity: string;
  operationStatus?: VersionControlOperationStatus | null;
}

export const useVersionControlLfsDialogBinding = ({
  remote,
  controller,
  requestIdentity,
  operationStatus,
}: UseVersionControlLfsDialogBindingOptions): {
  dialog: Omit<VersionControlLfsDialogProps, 'open' | 'onOpenChange'>;
  open: () => void;
  isPending: boolean;
} => {
  const patternsQuery = remote.useLfsPatternsQuery(controller.dialogs.lfsSettingsOpen);
  const updatePatternsMutation = remote.useUpdateLfsPatternsMutation();
  const previewSnapshotMutation = remote.usePreviewLfsSnapshotMutation();
  const convertSnapshotMutation = remote.useConvertLfsSnapshotMutation();
  const cancelOperationMutation = remote.useCancelOperationMutation();

  return {
    open: () => controller.dialogs.setLfsSettingsOpen(true),
    isPending: updatePatternsMutation.isPending
      || previewSnapshotMutation.isPending
      || convertSnapshotMutation.isPending
      || cancelOperationMutation.isPending,
    dialog: {
      requestIdentity,
      patterns: patternsQuery.data?.patterns ?? [],
      isPatternsLoading: patternsQuery.isLoading,
      patternsError: Boolean(patternsQuery.error),
      operationStatus: operationStatus ?? null,
      onReloadPatterns: patternsQuery.refetch,
      onSavePatterns: patterns => updatePatternsMutation.mutateAsync({ patterns }),
      onPreview: patterns => previewSnapshotMutation.mutateAsync({ patterns }),
      onConvert: paths => convertSnapshotMutation.mutateAsync({ paths }),
      onCancel: () => cancelOperationMutation.mutateAsync(),
    },
  };
};

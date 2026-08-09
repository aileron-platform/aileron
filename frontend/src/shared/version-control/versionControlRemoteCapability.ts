import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  shouldRetryVersionControlQuery,
  type VersionControlCore,
} from './versionControlSessionCore';
import type {
  VersionControlMutationResult,
  VersionControlRemoteBranches,
  VersionControlRemoteSettings,
  VersionControlRepositoryStatus,
  VersionControlStatus,
} from './types';
import type {
  VersionControlLfsPatterns,
  VersionControlLfsPatternsUpdatePayload,
  VersionControlLfsSnapshotConvertPayload,
  VersionControlLfsSnapshotPreview,
} from './versionControlLfs';

interface WorkspaceFetchPayload {
  remote?: string;
  prune?: boolean;
}

interface WorkspaceClonePayload {
  remoteUrl: string;
  branch?: string;
}

interface WorkspacePullPayload {
  remote?: string;
  branch?: string;
}

interface WorkspacePushPayload {
  remote?: string;
  branch?: string;
}

interface KnowledgeBaseFetchPayload {
  remote?: string;
}

interface KnowledgeBasePullPayload {
  remote?: string;
  branch?: string;
}

interface KnowledgeBasePushPayload {
  remote?: string;
  branch?: string;
}

export interface VersionControlInitializeRepositoryPayload {
  defaultBranch: string;
}

interface RemoteMutationTransport<FetchPayload, PullPayload, PushPayload> {
  fetch: (payload: FetchPayload) => Promise<unknown>;
  pull: (payload: PullPayload) => Promise<unknown>;
  push: (payload: PushPayload) => Promise<unknown>;
  setRemoteUrl: (remoteUrl: string) => Promise<unknown>;
}

const createRemoteMutationCapability = <
  FetchPayload,
  PullPayload,
  PushPayload,
>(
  core: VersionControlCore,
  transport: RemoteMutationTransport<FetchPayload, PullPayload, PushPayload>,
) => {
  const useFetchMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: transport.fetch,
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const usePullMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: transport.pull,
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const usePushMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: transport.push,
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useSetRemoteUrlMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: transport.setRemoteUrl,
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  return {
    useFetchMutation,
    usePullMutation,
    usePushMutation,
    useSetRemoteUrlMutation,
  };
};

const useRepositoryQueryForCore = (core: VersionControlCore, enabled = true) => useQuery({
  queryKey: core.key('remote', 'repository'),
  queryFn: () => core.request<VersionControlRepositoryStatus>('repository'),
  enabled: core.identityEnabled && enabled,
  retry: shouldRetryVersionControlQuery,
});

const createLfsCapability = (core: VersionControlCore) => {
  const useLfsPatternsQuery = (enabled = true) => useQuery({
    queryKey: core.key('remote', 'lfs-patterns'),
    queryFn: () => core.request<VersionControlLfsPatterns>('lfs'),
    enabled: core.gitQueriesEnabled && enabled,
    retry: shouldRetryVersionControlQuery,
  });

  const useUpdateLfsPatternsMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlLfsPatternsUpdatePayload) =>
        core.request<VersionControlMutationResult>('lfs', {
          method: 'POST',
          body: payload,
        }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'remote']),
    });
  };

  const usePreviewLfsSnapshotMutation = () => useMutation({
    mutationFn: (payload: VersionControlLfsPatternsUpdatePayload) =>
      core.request<VersionControlLfsSnapshotPreview>('lfs/preview', {
        method: 'POST',
        body: payload,
      }),
  });

  const useConvertLfsSnapshotMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlLfsSnapshotConvertPayload) =>
        core.request<VersionControlMutationResult>('lfs/convert', {
          method: 'POST',
          body: payload,
        }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'remote']),
    });
  };

  const useCancelOperationMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: () => core.request<VersionControlMutationResult>('operation/cancel', {
        method: 'POST',
      }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'remote']),
    });
  };

  return {
    useCancelOperationMutation,
    useConvertLfsSnapshotMutation,
    useLfsPatternsQuery,
    usePreviewLfsSnapshotMutation,
    useUpdateLfsPatternsMutation,
  };
};

export const createWorkspaceRemoteCapability = (core: VersionControlCore) => {
  const mutations = createRemoteMutationCapability<
    WorkspaceFetchPayload,
    WorkspacePullPayload,
    WorkspacePushPayload
  >(core, {
    fetch: (payload = {}) =>
      core.request<VersionControlMutationResult>('fetch', {
        method: 'POST',
        body: {
          remote: payload.remote ?? 'origin',
          prune: payload.prune ?? false,
        },
      }),
    pull: payload =>
      core.request<VersionControlMutationResult>('pull', {
        method: 'POST',
        body: {
          remote: payload.remote ?? 'origin',
          branch: payload.branch,
        },
      }),
    push: payload =>
      core.request<VersionControlMutationResult>('push', {
        method: 'POST',
        body: {
          remote: payload.remote ?? 'origin',
          branch: payload.branch,
        },
      }),
    setRemoteUrl: remoteUrl =>
      core.request<VersionControlRemoteSettings>('remote', {
        method: 'PUT',
        body: { remoteUrl },
      }),
  });

  const useRemoteSettingsQuery = (enabled = true) => useQuery({
    queryKey: core.key('remote', 'settings'),
    queryFn: () => core.request<VersionControlRemoteSettings>('remote'),
    enabled: core.gitQueriesEnabled && enabled,
    retry: shouldRetryVersionControlQuery,
  });

  const useRepositoryQuery = (enabled = true) =>
    useRepositoryQueryForCore(core, enabled);

  const useInitializeRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlInitializeRepositoryPayload) => core.request<VersionControlStatus>('init', {
        method: 'POST',
        body: payload,
      }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useCloneRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: WorkspaceClonePayload) =>
        core.request<VersionControlStatus>('clone', {
          method: 'POST',
          body: payload,
        }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useRemoteBranchesMutation = () => useMutation({
    mutationFn: (remoteUrl: string) =>
      core.request<VersionControlRemoteBranches>('remote-branches', {
        method: 'POST',
        body: { remoteUrl },
      }),
  });

  return {
    ...mutations,
    ...createLfsCapability(core),
    useCloneRepositoryMutation,
    useInitializeRepositoryMutation,
    useRemoteBranchesMutation,
    useRepositoryQuery,
    useRemoteSettingsQuery,
  };
};

export const createKnowledgeBaseRemoteCapability = (
  core: VersionControlCore,
) => {
  const mutations = createRemoteMutationCapability<
    KnowledgeBaseFetchPayload,
    KnowledgeBasePullPayload,
    KnowledgeBasePushPayload
  >(core, {
    fetch: (payload = {}) =>
      core.request<VersionControlMutationResult>('fetch', {
        method: 'POST',
        body: { remote: payload.remote ?? 'origin' },
      }),
    pull: payload =>
      core.request<VersionControlMutationResult>('pull', {
        method: 'POST',
        body: {
          remote: payload.remote ?? 'origin',
          branch: payload.branch,
        },
      }),
    push: payload =>
      core.request<VersionControlMutationResult>('push', {
        method: 'POST',
        body: {
          remote: payload.remote ?? 'origin',
          branch: payload.branch,
        },
      }),
    setRemoteUrl: remoteUrl =>
      core.request<VersionControlMutationResult>('remote', {
        method: 'PUT',
        body: { remoteUrl },
      }),
  });

  const useRepositoryQuery = (enabled = true) => useRepositoryQueryForCore(core, enabled);

  const useInitializeRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlInitializeRepositoryPayload) =>
        core.request<VersionControlStatus>('init', {
          method: 'POST',
          body: payload,
        }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useCloneRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: { remoteUrl: string; branch?: string }) =>
        core.request<VersionControlStatus>('clone', {
          method: 'POST',
          body: payload,
        }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useRemoteBranchesMutation = () => useMutation({
    mutationFn: (remoteUrl: string) =>
      core.request<VersionControlRemoteBranches>('remote-branches', {
        method: 'POST',
        body: { remoteUrl },
      }),
  });

  return {
    ...mutations,
    ...createLfsCapability(core),
    useRepositoryQuery,
    useInitializeRepositoryMutation,
    useCloneRepositoryMutation,
    useRemoteBranchesMutation,
  };
};

export const createMarketplaceRemoteCapability = (
  core: VersionControlCore,
) => {
  const mutations = createRemoteMutationCapability<void, void, void>(core, {
    fetch: () => core.request<VersionControlMutationResult>('fetch', { method: 'POST' }),
    pull: () => core.request<VersionControlMutationResult>('pull', { method: 'POST' }),
    push: () => core.request<VersionControlMutationResult>('push', { method: 'POST' }),
    setRemoteUrl: remoteUrl =>
      core.request<VersionControlMutationResult>('remote', {
        method: 'PUT',
        body: { remoteUrl },
      }),
  });

  const useRepositoryQuery = () => useRepositoryQueryForCore(core);

  const useInitializeRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlInitializeRepositoryPayload) =>
        core.request<VersionControlStatus>('init', { method: 'POST', body: payload }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useCloneRepositoryMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: { remoteUrl: string; branch?: string }) =>
        core.request<VersionControlStatus>('clone', { method: 'POST', body: payload }),
      onSuccess: () =>
        core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  const useRemoteBranchesMutation = () => useMutation({
    mutationFn: (remoteUrl: string) =>
      core.request<VersionControlRemoteBranches>('remote-branches', {
        method: 'POST',
        body: { remoteUrl },
      }),
  });

  return {
    ...mutations,
    ...createLfsCapability(core),
    useRepositoryQuery,
    useInitializeRepositoryMutation,
    useCloneRepositoryMutation,
    useRemoteBranchesMutation,
  };
};

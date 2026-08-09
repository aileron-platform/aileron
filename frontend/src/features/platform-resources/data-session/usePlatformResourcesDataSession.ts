import React from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import {
  getPlatformResourceCapacityTrend,
  getPlatformResourceResourceTrend,
  getPlatformResourceSummary,
  getWorkspaceCapacityExpansion,
  listPlatformKnowledgeBases,
  listPlatformWorkspaces,
  reassignPlatformResourceOwner,
  requestWorkspaceCapacityExpansion,
  searchPlatformResourceOwnerCandidates,
  updatePlatformKnowledgeBaseQuota,
} from '../api/platformResourcesApi';
import {
  resolvePlatformResourcePermissions,
  type PlatformResourcePermissions,
} from '../model/platformResourcePermissions';
import type { OperationId } from '@/shared/authorization/operationIds';
import type {
  PlatformResourceKind,
  PlatformKnowledgeBaseSummary,
  PlatformResourceListQuery,
  PlatformResourceOwnerReassignment,
  PlatformResourceRange,
  WorkspaceCapacityExpansionRequest,
  PlatformWorkspaceSummary,
  PlatformResourceSummary,
} from '../model/platformResourceTypes';

export type PlatformResourcesSection = 'management' | 'analytics';

export interface PlatformResourcesDataSessionInput {
  authSubject: string | null;
  kind: PlatformResourceKind;
  section: PlatformResourcesSection;
  range: PlatformResourceRange;
  listQuery: PlatformResourceListQuery;
  allowedOperations: readonly OperationId[];
}

type DialogSelectionType = 'ownerReassignment' | 'knowledgeBaseQuota' | 'capacityExpansion';

interface DialogSelection {
  type: DialogSelectionType;
  contextKey: string;
  identity: string;
  resourceId: string;
}

interface OwnerReassignmentCommand {
  contextKey: string;
  selectionKey: string;
  authSubject: string;
  kind: PlatformResourceKind;
  resourceId: string;
  payload: PlatformResourceOwnerReassignment;
}

interface KnowledgeBaseQuotaCommand {
  contextKey: string;
  selectionKey: string;
  authSubject: string;
  knowledgeBaseId: string;
  quotaBytes: number | null;
}

interface CapacityExpansionCommand {
  contextKey: string;
  selectionKey: string;
  authSubject: string;
  workspaceId: string;
  payload: WorkspaceCapacityExpansionRequest;
}

interface RefreshCommand {
  contextKey: string;
  authSubject: string;
  kind: PlatformResourceKind;
  section: PlatformResourcesSection;
  range: PlatformResourceRange;
  inventoryKey: readonly unknown[];
  summaryKey: readonly unknown[];
  resourceTrendKey: readonly unknown[];
  capacityTrendKey: readonly unknown[];
}

const queryKeys = {
  scope: (authSubject: string) => ['platform-resources', authSubject] as const,
  resourceKind: (authSubject: string, kind: PlatformResourceKind) => (
    [...queryKeys.scope(authSubject), 'resource', kind] as const
  ),
  inventory: (authSubject: string, kind: PlatformResourceKind) => (
    [...queryKeys.resourceKind(authSubject, kind), 'inventory'] as const
  ),
  inventoryPage: (
    contextKey: string,
    authSubject: string,
    kind: PlatformResourceKind,
    query: PlatformResourceListQuery,
  ) => (
    [...queryKeys.inventory(authSubject, kind), 'context', contextKey, query] as const
  ),
  analytics: (authSubject: string, kind: PlatformResourceKind) => (
    [...queryKeys.resourceKind(authSubject, kind), 'analytics'] as const
  ),
  statistic: (
    contextKey: string,
    authSubject: string,
    kind: PlatformResourceKind,
    metric: 'summary' | 'resource-trend' | 'capacity-trend',
    range: PlatformResourceRange,
  ) => [
    ...queryKeys.analytics(authSubject, kind),
    'context',
    contextKey,
    metric,
    range,
  ] as const,
  ownerCandidates: (
    contextKey: string,
    authSubject: string,
    resourceId: string,
    query: string,
  ) => (
    [...queryKeys.scope(authSubject), 'owner-candidates', contextKey, resourceId, query] as const
  ),
  capacityExpansion: (
    contextKey: string,
    authSubject: string,
    workspaceId: string,
    requestId: string,
  ) => (
    [
      ...queryKeys.resourceKind(authSubject, 'workspaces'),
      'capacity-expansion',
      contextKey,
      workspaceId,
      requestId,
    ] as const
  ),
};

const mutationNotAllowed = (): Error => new Error('PLATFORM_RESOURCE_MUTATION_NOT_ALLOWED');

const capacityExpansionMonitors = new WeakMap<QueryClient, Map<string, Promise<void>>>();

const waitForNextCapacityCheck = (delayMs: number) => new Promise<void>(resolve => {
  setTimeout(resolve, delayMs);
});

const invalidateWorkspaceProjections = async (
  queryClient: QueryClient,
  authSubject: string,
) => {
  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: queryKeys.inventory(authSubject, 'workspaces'),
    }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.analytics(authSubject, 'workspaces'),
    }),
  ]);
};

const ensureCapacityExpansionMonitor = (
  queryClient: QueryClient,
  contextKey: string,
  authSubject: string,
  workspaceId: string,
  requestId: string,
) => {
  let monitors = capacityExpansionMonitors.get(queryClient);
  if (!monitors) {
    monitors = new Map();
    capacityExpansionMonitors.set(queryClient, monitors);
  }
  const monitorKey = `${authSubject}:${workspaceId}:${requestId}`;
  if (monitors.has(monitorKey)) return;

  const monitor = (async () => {
    let consecutiveErrors = 0;
    while (true) {
      try {
        const status = await getWorkspaceCapacityExpansion(
          workspaceId,
          requestId,
          new AbortController().signal,
        );
        queryClient.setQueryData(
          queryKeys.capacityExpansion(contextKey, authSubject, workspaceId, requestId),
          status,
        );
        consecutiveErrors = 0;
        if (status.phase === 'completed' || status.phase === 'failed') {
          await invalidateWorkspaceProjections(queryClient, authSubject);
          return;
        }
        await waitForNextCapacityCheck(2000);
      } catch {
        consecutiveErrors += 1;
        await waitForNextCapacityCheck(Math.min(1000 * (2 ** (consecutiveErrors - 1)), 10000));
      }
    }
  })().finally(() => {
    monitors?.delete(monitorKey);
  });
  monitors.set(monitorKey, monitor);
};

const buildContextSignature = (
  subject: string,
  kind: PlatformResourceKind,
  section: PlatformResourcesSection,
  range: PlatformResourceRange,
  listQuery: PlatformResourceListQuery,
  permissions: PlatformResourcePermissions,
): string => JSON.stringify({
  subject,
  kind,
  section,
  range,
  listQuery: {
    q: listQuery.q,
    page: listQuery.page,
    pageSize: listQuery.pageSize,
    health: listQuery.health ?? null,
    visibility: listQuery.visibility ?? null,
    indexingHealth: listQuery.indexingHealth ?? null,
    capacityRisk: listQuery.capacityRisk ?? null,
    sort: listQuery.sort ?? null,
    order: listQuery.order ?? null,
  },
  permissions: {
    canRead: permissions.canRead,
    canReassignOwner: permissions.canReassignOwner,
    canManageKnowledgeBaseQuota: permissions.canManageKnowledgeBaseQuota,
    canExpandWorkspaceCapacity: permissions.canExpandWorkspaceCapacity,
  },
});

export const usePlatformResourcesDataSession = ({
  authSubject,
  kind,
  section,
  range,
  listQuery,
  allowedOperations,
}: PlatformResourcesDataSessionInput) => {
  const queryClient = useQueryClient();
  const permissions = React.useMemo(
    () => resolvePlatformResourcePermissions(allowedOperations),
    [allowedOperations],
  );
  const [candidateSearch, setCandidateSearch] = React.useState({ identity: '', query: '' });
  const [selection, setSelection] = React.useState<DialogSelection | null>(null);
  const selectionSequenceRef = React.useRef(0);
  const subject = authSubject ?? '';
  const canRead = permissions.canRead && subject.length > 0;
  const contextSignature = buildContextSignature(
    subject,
    kind,
    section,
    range,
    listQuery,
    permissions,
  );
  const contextBoundaryRef = React.useRef<{ signature: string; generation: number } | null>(null);
  if (
    contextBoundaryRef.current === null
    || contextBoundaryRef.current.signature !== contextSignature
  ) {
    contextBoundaryRef.current = {
      signature: contextSignature,
      generation: (contextBoundaryRef.current?.generation ?? -1) + 1,
    };
  }
  const generation = contextBoundaryRef.current.generation;
  const contextKey = `${contextSignature}:${generation}`;
  const contextRef = React.useRef({ key: contextKey, generation });
  contextRef.current = { key: contextKey, generation };
  const isCurrentContext = React.useCallback(
    (key: string) => contextRef.current.key === key,
    [],
  );

  const activeSelection = selection?.contextKey === contextKey ? selection : null;
  const ownerSelection = activeSelection?.type === 'ownerReassignment' ? activeSelection : null;
  const quotaSelection = activeSelection?.type === 'knowledgeBaseQuota' ? activeSelection : null;
  const expansionSelection = activeSelection?.type === 'capacityExpansion' ? activeSelection : null;
  const ownerResourceId = ownerSelection?.resourceId ?? null;
  const quotaResourceId = quotaSelection?.resourceId ?? null;
  const expansionWorkspaceId = expansionSelection?.resourceId ?? null;
  const ownerSearchIdentity = ownerSelection?.identity ?? '';
  const candidateQuery = candidateSearch.identity === ownerSearchIdentity
    ? candidateSearch.query
    : '';

  const inventoryKey = queryKeys.inventoryPage(contextKey, subject, kind, listQuery);
  const inventoryQuery = useQuery({
    queryKey: inventoryKey,
    queryFn: ({ signal }) => (
      kind === 'workspaces'
        ? listPlatformWorkspaces(listQuery, signal)
        : listPlatformKnowledgeBases(listQuery, signal)
    ),
    enabled: canRead && section === 'management',
    staleTime: 0,
  });

  const summaryKey = queryKeys.statistic(contextKey, subject, kind, 'summary', range);
  const summaryQuery = useQuery({
    queryKey: summaryKey,
    queryFn: ({ signal }) => getPlatformResourceSummary(kind, range, false, signal),
    enabled: canRead && section === 'analytics',
    staleTime: 0,
  });
  const resourceTrendKey = queryKeys.statistic(
    contextKey,
    subject,
    kind,
    'resource-trend',
    range,
  );
  const resourceTrendQuery = useQuery({
    queryKey: resourceTrendKey,
    queryFn: ({ signal }) => getPlatformResourceResourceTrend(kind, range, false, signal),
    enabled: canRead && section === 'analytics',
    staleTime: 0,
  });
  const capacityTrendKey = queryKeys.statistic(
    contextKey,
    subject,
    kind,
    'capacity-trend',
    range,
  );
  const capacityTrendQuery = useQuery({
    queryKey: capacityTrendKey,
    queryFn: ({ signal }) => getPlatformResourceCapacityTrend(kind, range, false, signal),
    enabled: canRead && section === 'analytics',
    staleTime: 0,
  });

  const candidatesQuery = useQuery({
    queryKey: queryKeys.ownerCandidates(
      contextKey,
      subject,
      ownerResourceId ?? '',
      candidateQuery,
    ),
    queryFn: ({ signal }) => searchPlatformResourceOwnerCandidates(candidateQuery, signal),
    enabled: canRead
      && section === 'management'
      && permissions.canReassignOwner
      && ownerResourceId !== null
      && candidateQuery.length > 0,
    staleTime: 0,
  });

  const reassignMutation = useMutation({
    mutationFn: async (command: OwnerReassignmentCommand) => (
      reassignPlatformResourceOwner(command.kind, command.resourceId, command.payload)
    ),
    onSuccess: async (_data, command) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.inventory(command.authSubject, command.kind),
      });
    },
  });

  const quotaMutation = useMutation({
    mutationFn: async (command: KnowledgeBaseQuotaCommand) => (
      updatePlatformKnowledgeBaseQuota(command.knowledgeBaseId, command.quotaBytes)
    ),
    onSuccess: async (_data, command) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.resourceKind(command.authSubject, 'knowledge-bases'),
      });
    },
  });

  const expansionMutation = useMutation({
    mutationFn: async (command: CapacityExpansionCommand) => (
      requestWorkspaceCapacityExpansion(command.workspaceId, command.payload)
    ),
    onSuccess: async (data, command) => {
      queryClient.setQueryData(
        queryKeys.capacityExpansion(
          command.contextKey,
          command.authSubject,
          command.workspaceId,
          data.requestId,
        ),
        data,
      );
      ensureCapacityExpansionMonitor(
        queryClient,
        command.contextKey,
        command.authSubject,
        command.workspaceId,
        data.requestId,
      );
      await invalidateWorkspaceProjections(queryClient, command.authSubject);
    },
  });
  const expansionIdentity = expansionMutation.data
    && expansionMutation.variables?.selectionKey === expansionSelection?.identity
    && expansionMutation.variables?.contextKey === contextKey
    && expansionMutation.variables?.authSubject === subject
    && expansionMutation.variables.workspaceId === expansionWorkspaceId
    && expansionMutation.data.workspaceId === expansionWorkspaceId
    ? expansionMutation.data
    : null;
  const expansionStatusQuery = useQuery({
    queryKey: queryKeys.capacityExpansion(
      contextKey,
      subject,
      expansionIdentity?.workspaceId ?? '',
      expansionIdentity?.requestId ?? '',
    ),
    queryFn: ({ signal }) => getWorkspaceCapacityExpansion(
      expansionIdentity?.workspaceId ?? '',
      expansionIdentity?.requestId ?? '',
      signal,
    ),
    enabled: canRead
      && section === 'management'
      && permissions.canExpandWorkspaceCapacity
      && expansionIdentity !== null,
    staleTime: 2000,
  });
  const expansionStatus = expansionIdentity !== null
    && expansionStatusQuery.data?.workspaceId === expansionIdentity.workspaceId
    && expansionStatusQuery.data.requestId === expansionIdentity.requestId
    ? expansionStatusQuery.data
    : expansionIdentity;

  const refreshMutation = useMutation({
    mutationFn: async (command: RefreshCommand) => {
      if (!isCurrentContext(command.contextKey) || !canRead) return;
      if (command.section === 'management') {
        await queryClient.invalidateQueries({
          queryKey: command.inventoryKey,
          exact: true,
        });
        return;
      }
      const refreshes = [
        {
          queryKey: command.summaryKey,
          queryFn: ({ signal }: { signal: AbortSignal }) => (
            getPlatformResourceSummary(command.kind, command.range, true, signal)
          ),
        },
        {
          queryKey: command.resourceTrendKey,
          queryFn: ({ signal }: { signal: AbortSignal }) => (
            getPlatformResourceResourceTrend(command.kind, command.range, true, signal)
          ),
        },
        {
          queryKey: command.capacityTrendKey,
          queryFn: ({ signal }: { signal: AbortSignal }) => (
            getPlatformResourceCapacityTrend(command.kind, command.range, true, signal)
          ),
        },
      ];
      await Promise.allSettled(refreshes.map(async refresh => {
        await queryClient.cancelQueries({ queryKey: refresh.queryKey, exact: true });
        await queryClient.fetchQuery({
          queryKey: refresh.queryKey,
          queryFn: refresh.queryFn,
          staleTime: 0,
        });
      }));
    },
  });

  const createSelection = React.useCallback((
    type: DialogSelectionType,
    resourceId: string,
  ): DialogSelection => {
    selectionSequenceRef.current += 1;
    return {
      type,
      contextKey,
      identity: `${contextKey}:${selectionSequenceRef.current}`,
      resourceId,
    };
  }, [contextKey]);

  const openOwnerReassignment = React.useCallback((resource: PlatformResourceSummary) => {
    if (!canRead || section !== 'management' || !permissions.canReassignOwner) return;
    setSelection(createSelection('ownerReassignment', resource.id));
  }, [canRead, createSelection, permissions.canReassignOwner, section]);

  const openKnowledgeBaseQuota = React.useCallback((resource: PlatformKnowledgeBaseSummary) => {
    if (
      !canRead
      || section !== 'management'
      || kind !== 'knowledge-bases'
      || !permissions.canManageKnowledgeBaseQuota
    ) return;
    setSelection(createSelection('knowledgeBaseQuota', resource.id));
  }, [canRead, createSelection, kind, permissions.canManageKnowledgeBaseQuota, section]);

  const openCapacityExpansion = React.useCallback((resource: PlatformWorkspaceSummary) => {
    if (
      !canRead
      || section !== 'management'
      || kind !== 'workspaces'
      || !permissions.canExpandWorkspaceCapacity
    ) return;
    setSelection(createSelection('capacityExpansion', resource.id));
  }, [canRead, createSelection, kind, permissions.canExpandWorkspaceCapacity, section]);

  const resetOwnerReassignment = React.useCallback(() => {
    if (ownerResourceId && candidateQuery) {
      void queryClient.cancelQueries({
        queryKey: queryKeys.ownerCandidates(
          contextKey,
          subject,
          ownerResourceId,
          candidateQuery,
        ),
        exact: true,
      });
    }
    setCandidateSearch({ identity: '', query: '' });
    reassignMutation.reset();
    setSelection(previous => (
      previous?.contextKey === contextKey && previous.type === 'ownerReassignment'
        ? null
        : previous
    ));
  }, [candidateQuery, contextKey, ownerResourceId, queryClient, reassignMutation, subject]);

  const resetKnowledgeBaseQuota = React.useCallback(() => {
    quotaMutation.reset();
    setSelection(previous => (
      previous?.contextKey === contextKey && previous.type === 'knowledgeBaseQuota'
        ? null
        : previous
    ));
  }, [contextKey, quotaMutation]);

  const resetCapacityExpansion = React.useCallback(() => {
    expansionMutation.reset();
    setSelection(previous => (
      previous?.contextKey === contextKey && previous.type === 'capacityExpansion'
        ? null
        : previous
    ));
  }, [contextKey, expansionMutation]);

  const submitOwnerReassignment = React.useCallback(async (
    payload: PlatformResourceOwnerReassignment,
  ) => {
    if (
      !isCurrentContext(contextKey)
      || !canRead
      || section !== 'management'
      || !permissions.canReassignOwner
      || !ownerSelection
    ) {
      throw mutationNotAllowed();
    }
    await reassignMutation.mutateAsync({
      contextKey,
      selectionKey: ownerSelection.identity,
      authSubject: subject,
      kind,
      resourceId: ownerSelection.resourceId,
      payload,
    });
  }, [
    canRead,
    contextKey,
    isCurrentContext,
    kind,
    ownerSelection,
    permissions.canReassignOwner,
    reassignMutation,
    section,
    subject,
  ]);

  const submitKnowledgeBaseQuota = React.useCallback(async (quotaBytes: number | null) => {
    if (
      !isCurrentContext(contextKey)
      || !canRead
      || section !== 'management'
      || kind !== 'knowledge-bases'
      || !permissions.canManageKnowledgeBaseQuota
      || !quotaSelection
    ) {
      throw mutationNotAllowed();
    }
    await quotaMutation.mutateAsync({
      contextKey,
      selectionKey: quotaSelection.identity,
      authSubject: subject,
      knowledgeBaseId: quotaSelection.resourceId,
      quotaBytes,
    });
  }, [
    canRead,
    contextKey,
    isCurrentContext,
    kind,
    permissions.canManageKnowledgeBaseQuota,
    quotaMutation,
    quotaSelection,
    section,
    subject,
  ]);

  const submitCapacityExpansion = React.useCallback(async (
    payload: WorkspaceCapacityExpansionRequest,
  ) => {
    if (
      !isCurrentContext(contextKey)
      || !canRead
      || section !== 'management'
      || kind !== 'workspaces'
      || !permissions.canExpandWorkspaceCapacity
      || !expansionSelection
    ) {
      throw mutationNotAllowed();
    }
    await expansionMutation.mutateAsync({
      contextKey,
      selectionKey: expansionSelection.identity,
      authSubject: subject,
      workspaceId: expansionSelection.resourceId,
      payload,
    });
  }, [
    canRead,
    contextKey,
    expansionMutation,
    expansionSelection,
    isCurrentContext,
    kind,
    permissions.canExpandWorkspaceCapacity,
    section,
    subject,
  ]);

  const searchOwnerCandidates = React.useCallback(async (query: string) => {
    if (
      !isCurrentContext(contextKey)
      || !canRead
      || section !== 'management'
      || !permissions.canReassignOwner
      || !ownerSelection
    ) return;
    const normalizedQuery = query.trim();
    if (normalizedQuery === candidateQuery && normalizedQuery.length > 0) {
      await candidatesQuery.refetch();
      return;
    }
    setCandidateSearch({ identity: ownerSelection.identity, query: normalizedQuery });
  }, [
    candidateQuery,
    candidatesQuery,
    canRead,
    contextKey,
    isCurrentContext,
    ownerSelection,
    permissions.canReassignOwner,
    section,
  ]);

  const previousBoundaryRef = React.useRef({
    contextKey,
    ownerSelectionKey: ownerSelection?.identity ?? null,
    quotaSelectionKey: quotaSelection?.identity ?? null,
    expansionSelectionKey: expansionSelection?.identity ?? null,
  });

  React.useEffect(() => {
    const previous = previousBoundaryRef.current;
    const contextChanged = previous.contextKey !== contextKey;
    const ownerSelectionKey = ownerSelection?.identity ?? null;
    const quotaSelectionKey = quotaSelection?.identity ?? null;
    const expansionSelectionKey = expansionSelection?.identity ?? null;
    const ownerSelectionChanged = previous.ownerSelectionKey !== ownerSelectionKey;
    const quotaSelectionChanged = previous.quotaSelectionKey !== quotaSelectionKey;
    const expansionSelectionChanged = previous.expansionSelectionKey !== expansionSelectionKey;

    if (contextChanged || ownerSelectionChanged) {
      setCandidateSearch({ identity: '', query: '' });
      reassignMutation.reset();
    }
    if (contextChanged || quotaSelectionChanged) quotaMutation.reset();
    if (contextChanged || expansionSelectionChanged) expansionMutation.reset();
    if (contextChanged) {
      refreshMutation.reset();
      setSelection(null);
    }
    previousBoundaryRef.current = {
      contextKey,
      ownerSelectionKey,
      quotaSelectionKey,
      expansionSelectionKey,
    };
  }, [
    contextKey,
    expansionMutation,
    expansionSelection?.identity,
    ownerSelection?.identity,
    quotaMutation,
    quotaSelection?.identity,
    reassignMutation,
    refreshMutation,
  ]);

  const activeReassignmentMutation = Boolean(
    reassignMutation.variables?.contextKey === contextKey
    && reassignMutation.variables.selectionKey === ownerSelection?.identity
    && reassignMutation.variables.authSubject === subject
    && reassignMutation.variables.kind === kind
    && reassignMutation.variables.resourceId === ownerResourceId,
  );
  const activeQuotaMutation = Boolean(
    quotaMutation.variables?.contextKey === contextKey
    && quotaMutation.variables.selectionKey === quotaSelection?.identity
    && quotaMutation.variables.authSubject === subject
    && quotaMutation.variables.knowledgeBaseId === quotaResourceId,
  );
  const activeExpansionMutation = Boolean(
    expansionMutation.variables?.contextKey === contextKey
    && expansionMutation.variables.selectionKey === expansionSelection?.identity
    && expansionMutation.variables.authSubject === subject
    && expansionMutation.variables.workspaceId === expansionWorkspaceId,
  );
  const activeRefresh = refreshMutation.variables?.contextKey === contextKey;

  const inventory = canRead ? inventoryQuery.data : undefined;
  const selectedOwnerResource = inventory?.items.find(item => item.id === ownerResourceId) ?? null;
  const selectedQuotaResource = kind === 'knowledge-bases'
    ? (inventory?.items.find(item => item.id === quotaResourceId) as PlatformKnowledgeBaseSummary | undefined) ?? null
    : null;
  const selectedExpansionResource = kind === 'workspaces'
    ? (inventory?.items.find(item => item.id === expansionWorkspaceId) as PlatformWorkspaceSummary | undefined) ?? null
    : null;

  const retryInventory = React.useCallback(async () => {
    if (!isCurrentContext(contextKey)) return;
    await inventoryQuery.refetch();
  }, [contextKey, inventoryQuery, isCurrentContext]);
  const retrySummary = React.useCallback(async () => {
    if (!isCurrentContext(contextKey)) return;
    await summaryQuery.refetch();
  }, [contextKey, isCurrentContext, summaryQuery]);
  const retryResourceTrend = React.useCallback(async () => {
    if (!isCurrentContext(contextKey)) return;
    await resourceTrendQuery.refetch();
  }, [contextKey, isCurrentContext, resourceTrendQuery]);
  const retryCapacityTrend = React.useCallback(async () => {
    if (!isCurrentContext(contextKey)) return;
    await capacityTrendQuery.refetch();
  }, [capacityTrendQuery, contextKey, isCurrentContext]);
  const runRefresh = React.useCallback(async () => {
    if (!isCurrentContext(contextKey) || !canRead) return;
    await refreshMutation.mutateAsync({
      contextKey,
      authSubject: subject,
      kind,
      section,
      range,
      inventoryKey,
      summaryKey,
      resourceTrendKey,
      capacityTrendKey,
    });
  }, [
    authSubject,
    canRead,
    capacityTrendKey,
    contextKey,
    inventoryKey,
    isCurrentContext,
    kind,
    range,
    refreshMutation,
    resourceTrendKey,
    section,
    subject,
    summaryKey,
  ]);

  return {
    permissions,
    inventory: {
      items: inventory?.items ?? [],
      total: inventory?.total ?? 0,
      isLoading: inventoryQuery.isPending,
      hasError: inventoryQuery.isError,
      retry: retryInventory,
    },
    analytics: {
      summary: {
        data: canRead ? summaryQuery.data ?? null : null,
        isLoading: summaryQuery.isPending,
        hasError: summaryQuery.isError,
        retry: retrySummary,
      },
      resourceTrend: {
        data: canRead ? resourceTrendQuery.data ?? null : null,
        isLoading: resourceTrendQuery.isPending,
        hasError: resourceTrendQuery.isError,
        retry: retryResourceTrend,
      },
      capacityTrend: {
        data: canRead ? capacityTrendQuery.data ?? null : null,
        isLoading: capacityTrendQuery.isPending,
        hasError: capacityTrendQuery.isError,
        retry: retryCapacityTrend,
      },
    },
    refresh: {
      run: runRefresh,
      isRefreshing: activeRefresh && refreshMutation.isPending,
    },
    commands: {
      openOwnerReassignment,
      openKnowledgeBaseQuota,
      openCapacityExpansion,
    },
    dialogs: {
      ownerReassignment: {
        selectionIdentity: ownerSelection?.identity ?? null,
        resource: selectedOwnerResource,
        candidates: candidatesQuery.data ?? [],
        isSearching: candidatesQuery.isFetching,
        searchError: candidatesQuery.isError,
        search: searchOwnerCandidates,
        submit: submitOwnerReassignment,
        isSubmitting: activeReassignmentMutation && reassignMutation.isPending,
        submitError: activeReassignmentMutation && reassignMutation.isError,
        reset: resetOwnerReassignment,
      },
      knowledgeBaseQuota: {
        selectionIdentity: quotaSelection?.identity ?? null,
        resource: selectedQuotaResource,
        submit: submitKnowledgeBaseQuota,
        isSubmitting: activeQuotaMutation && quotaMutation.isPending,
        hasError: activeQuotaMutation && quotaMutation.isError,
        reset: resetKnowledgeBaseQuota,
      },
      capacityExpansion: {
        contextKey,
        resource: selectedExpansionResource,
        submit: submitCapacityExpansion,
        status: expansionStatus,
        isSubmitting: activeExpansionMutation && expansionMutation.isPending,
        hasError: (activeExpansionMutation && expansionMutation.isError)
          || (expansionIdentity !== null && expansionStatusQuery.isError),
        reset: resetCapacityExpansion,
      },
    },
  };
};

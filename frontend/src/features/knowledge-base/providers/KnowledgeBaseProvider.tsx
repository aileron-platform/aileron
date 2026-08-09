import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { createLogger } from '@/shared/services/logger';
import { useI18n } from '@/shared/hooks/useI18n';
import * as knowledgeBaseApi from '@/features/knowledge-base/api/knowledgeBaseApi';
import type {
  KnowledgeBaseCreatePayload,
  KnowledgeBaseDetail,
  KnowledgeBaseShareCreatePayload,
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareUpdatePayload,
  KnowledgeBaseSummary,
  KnowledgeBaseUpdatePayload,
  KnowledgeBaseVisibilityUpdatePayload,
  KnowledgeBaseWorkspaceUsageResponse,
} from '@/features/knowledge-base/model/knowledgeBaseTypes';
import { resolveKnowledgeBasePermissions } from '@/features/knowledge-base/model/knowledgeBasePermissions';
import { isKnowledgeBaseAuthorizationDenialCode } from '@/shared/authorization/authorizationErrorCodes';
import { clearKnowledgeBaseArchiveOperations } from '@/features/knowledge-base/model/knowledgeBaseArchivePersistence';

interface KnowledgeBaseProviderProps {
  children: React.ReactNode;
}

interface KnowledgeBaseContextValue {
  isReady: boolean;
  knowledgeBases: KnowledgeBaseSummary[];
  attachmentCounts: Record<string, number>;
  isLoadingKnowledgeBases: boolean;
  listError: string | null;
  detailById: Record<string, KnowledgeBaseDetail | undefined>;
  sharesById: Record<string, KnowledgeBaseShareSummary[] | undefined>;
  workspaceUsageById: Record<string, KnowledgeBaseWorkspaceUsageResponse | undefined>;
  isMutating: boolean;
  reloadKnowledgeBases: () => Promise<void>;
  createKnowledgeBase: (payload: KnowledgeBaseCreatePayload) => Promise<KnowledgeBaseDetail>;
  updateKnowledgeBase: (kbId: string, payload: KnowledgeBaseUpdatePayload) => Promise<KnowledgeBaseDetail>;
  updateKnowledgeBaseVisibility: (kbId: string, payload: KnowledgeBaseVisibilityUpdatePayload) => Promise<KnowledgeBaseDetail>;
  deleteKnowledgeBase: (kbId: string, confirmationName: string) => Promise<void>;
  loadKnowledgeBaseDetail: (kbId: string) => Promise<KnowledgeBaseDetail>;
  loadKnowledgeBaseShares: (kbId: string) => Promise<KnowledgeBaseShareSummary[]>;
  loadKnowledgeBaseWorkspaceUsage: (kbId: string) => Promise<KnowledgeBaseWorkspaceUsageResponse>;
  createKnowledgeBaseShare: (kbId: string, payload: KnowledgeBaseShareCreatePayload) => Promise<KnowledgeBaseShareSummary>;
  updateKnowledgeBaseShare: (kbId: string, shareId: string, payload: KnowledgeBaseShareUpdatePayload) => Promise<KnowledgeBaseShareSummary>;
  deleteKnowledgeBaseShare: (kbId: string, shareId: string) => Promise<void>;
}

const KnowledgeBaseContext = createContext<KnowledgeBaseContextValue | undefined>(undefined);
const logger = createLogger('KnowledgeBaseProvider');
const EMPTY_USAGE: KnowledgeBaseWorkspaceUsageResponse = {
  visibleItems: [],
  hiddenWorkspaceCount: 0,
  attachmentCount: 0,
};

const createKnowledgeBasePermissionError = (message: string): Error & { errorCode: string } => (
  Object.assign(new Error(message), { errorCode: 'KB_PERMISSION_DENIED' })
);

interface KnowledgeBaseAuthorizationSnapshot {
  accessRole: unknown;
  allowedOperations: unknown;
  generation: number;
}

const isKnowledgeBaseQueryKey = (
  queryKey: QueryKey,
  knowledgeBaseId: string,
): boolean => (
  (
    queryKey[0] === 'version-control'
    && queryKey[1] === 'knowledge-bases'
    && queryKey[2] === knowledgeBaseId
  )
  || queryKey.some((part) => (
    (
      typeof part === 'object'
      && part !== null
      && 'knowledgeBaseId' in part
      && part.knowledgeBaseId === knowledgeBaseId
    )
    || (
      typeof part === 'string'
      && part.includes(`/knowledge-bases/${knowledgeBaseId}/`)
    )
  ))
);

export const KnowledgeBaseProvider: React.FC<KnowledgeBaseProviderProps> = ({ children }) => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [attachmentCounts, setAttachmentCounts] = useState<Record<string, number>>({});
  const [detailById, setDetailById] = useState<Record<string, KnowledgeBaseDetail | undefined>>({});
  const [sharesById, setSharesById] = useState<Record<string, KnowledgeBaseShareSummary[] | undefined>>({});
  const [workspaceUsageById, setWorkspaceUsageById] = useState<Record<string, KnowledgeBaseWorkspaceUsageResponse | undefined>>({});
  const [isLoadingKnowledgeBases, setIsLoadingKnowledgeBases] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);
  const currentAccessRoleByIdRef = useRef<Record<
    string,
    KnowledgeBaseAuthorizationSnapshot | undefined
  >>({});
  const detailByIdRef = useRef<Record<string, KnowledgeBaseDetail | undefined>>({});
  const authorizationGenerationRef = useRef(0);
  const latestAppliedListGenerationRef = useRef(0);

  const nextAuthorizationGeneration = useCallback(() => {
    authorizationGenerationRef.current += 1;
    return authorizationGenerationRef.current;
  }, []);

  const requireCurrentPermission = useCallback((
    kbId: string,
    requirement: 'read' | 'settings' | 'shares' | 'visibility' | 'delete',
  ) => {
    const permissions = resolveKnowledgeBasePermissions(
      currentAccessRoleByIdRef.current[kbId]?.accessRole,
      currentAccessRoleByIdRef.current[kbId]?.allowedOperations,
    );
    const isAllowed = {
      read: permissions.canRead,
      settings: permissions.canManageSettings,
      shares: permissions.canManageShares,
      visibility: permissions.canManageVisibility,
      delete: permissions.canDelete,
    }[requirement];
    if (!isAllowed) {
      throw createKnowledgeBasePermissionError(t('common.authorization.accessDeniedDescription'));
    }
  }, [t]);

  const clearManagerOnlyData = useCallback((kbId: string) => {
    setSharesById((current) => {
      const next = { ...current };
      delete next[kbId];
      return next;
    });
    setWorkspaceUsageById((current) => {
      const next = { ...current };
      delete next[kbId];
      return next;
    });
    setAttachmentCounts((current) => {
      const next = { ...current };
      delete next[kbId];
      return next;
    });
  }, []);

  const clearKnowledgeBaseResourceState = useCallback((kbId: string) => {
    delete currentAccessRoleByIdRef.current[kbId];
    delete detailByIdRef.current[kbId];
    setKnowledgeBases((current) => current.filter((item) => item.id !== kbId));
    setDetailById((current) => {
      if (current[kbId] === undefined) {
        return current;
      }
      const next = { ...current };
      delete next[kbId];
      return next;
    });
    clearManagerOnlyData(kbId);
    clearKnowledgeBaseArchiveOperations(kbId);
    const queryFilter = {
      predicate: (query: { queryKey: QueryKey }) => (
        isKnowledgeBaseQueryKey(query.queryKey, kbId)
      ),
    };
    void queryClient.cancelQueries(queryFilter);
    queryClient.removeQueries(queryFilter);
  }, [clearManagerOnlyData, queryClient]);

  const loadKnowledgeBaseWorkspaceUsage = useCallback(async (kbId: string) => {
    requireCurrentPermission(kbId, 'read');
    const usage = await knowledgeBaseApi.getKnowledgeBaseWorkspaceUsage(kbId);
    requireCurrentPermission(kbId, 'read');
    setWorkspaceUsageById((current) => ({ ...current, [kbId]: usage }));
    setAttachmentCounts((current) => ({ ...current, [kbId]: usage.attachmentCount }));
    return usage;
  }, [requireCurrentPermission]);

  const loadKnowledgeBaseShares = useCallback(async (kbId: string) => {
    requireCurrentPermission(kbId, 'read');
    const items = await knowledgeBaseApi.listKnowledgeBaseShares(kbId);
    requireCurrentPermission(kbId, 'read');
    setSharesById((current) => ({ ...current, [kbId]: items }));
    return items;
  }, [requireCurrentPermission]);

  const loadKnowledgeBaseDetail = useCallback(async (kbId: string) => {
    const generation = nextAuthorizationGeneration();
    currentAccessRoleByIdRef.current[kbId] = {
      accessRole: currentAccessRoleByIdRef.current[kbId]?.accessRole,
      allowedOperations:
        currentAccessRoleByIdRef.current[kbId]?.allowedOperations,
      generation,
    };
    try {
      const detail = await knowledgeBaseApi.getKnowledgeBase(kbId);
      const currentSnapshot = currentAccessRoleByIdRef.current[kbId];
      if (currentSnapshot?.generation !== generation) {
        const currentPermissions = resolveKnowledgeBasePermissions(
          currentSnapshot?.accessRole,
          currentSnapshot?.allowedOperations,
        );
        if (!currentPermissions.canRead || !currentPermissions.accessRole) {
          return detailByIdRef.current[kbId] ?? detail;
        }
        const normalizedDetail = {
          ...detail,
          accessRole: currentPermissions.accessRole,
          allowedOperations: currentPermissions.allowedOperations,
        };
        detailByIdRef.current[kbId] = normalizedDetail;
        setDetailById((current) => ({
          ...current,
          [kbId]: normalizedDetail,
        }));
        return normalizedDetail;
      }
      const permissions = resolveKnowledgeBasePermissions(
        detail.accessRole,
        detail.allowedOperations,
      );
      if (!permissions.canRead || !permissions.accessRole) {
        clearKnowledgeBaseResourceState(kbId);
        return detail;
      }
      currentAccessRoleByIdRef.current[kbId] = {
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
        generation,
      };
      const normalizedDetail = {
        ...detail,
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
      };
      detailByIdRef.current[kbId] = normalizedDetail;
      setDetailById((current) => ({ ...current, [kbId]: normalizedDetail }));
      setKnowledgeBases((current) => (
        current.some((item) => item.id === kbId)
          ? current.map((item) => (
            item.id === kbId ? normalizedDetail : item
          ))
          : [normalizedDetail, ...current]
      ));
      return normalizedDetail;
    } catch (error) {
      const errorCode = (
        error
        && typeof error === 'object'
        && 'errorCode' in error
      )
        ? error.errorCode
        : undefined;
      const status = (
        error
        && typeof error === 'object'
        && 'status' in error
      )
        ? error.status
        : undefined;
      if (
        (
          status === 403
          || isKnowledgeBaseAuthorizationDenialCode(errorCode)
        )
        && currentAccessRoleByIdRef.current[kbId]?.generation === generation
      ) {
        clearKnowledgeBaseResourceState(kbId);
      }
      throw error;
    }
  }, [
    clearKnowledgeBaseResourceState,
    nextAuthorizationGeneration,
  ]);

  const reloadKnowledgeBases = useCallback(async () => {
    const generation = nextAuthorizationGeneration();
    setIsLoadingKnowledgeBases(true);
    setListError(null);
    try {
      const items = await knowledgeBaseApi.listKnowledgeBases();
      if (generation < latestAppliedListGenerationRef.current) {
        return;
      }
      latestAppliedListGenerationRef.current = generation;
      const responseIds = new Set(items.map((item) => item.id));
      Object.entries(currentAccessRoleByIdRef.current).forEach(([kbId, snapshot]) => {
        if (
          snapshot
          && snapshot.generation <= generation
          && !responseIds.has(kbId)
        ) {
          clearKnowledgeBaseResourceState(kbId);
        }
      });

      items.forEach((item) => {
        const currentSnapshot = currentAccessRoleByIdRef.current[item.id];
        if (currentSnapshot && currentSnapshot.generation > generation) {
          return;
        }
        const permissions = resolveKnowledgeBasePermissions(
          item.accessRole,
          item.allowedOperations,
        );
        if (!permissions.canRead || !permissions.accessRole) {
          clearKnowledgeBaseResourceState(item.id);
          return;
        }
        currentAccessRoleByIdRef.current[item.id] = {
          accessRole: permissions.accessRole,
          allowedOperations: permissions.allowedOperations,
          generation,
        };
        const cachedDetail = detailByIdRef.current[item.id];
        if (cachedDetail && cachedDetail.accessRole !== permissions.accessRole) {
          const nextDetail = {
            ...cachedDetail,
            accessRole: permissions.accessRole,
            allowedOperations: permissions.allowedOperations,
          };
          detailByIdRef.current[item.id] = nextDetail;
          setDetailById((current) => (
            current[item.id] === undefined
              ? current
              : { ...current, [item.id]: nextDetail }
          ));
        }
      });

      setKnowledgeBases((current) => {
        const currentById = new Map(current.map((item) => [item.id, item]));
        const acceptedItems = items.filter((item) => {
          const snapshot = currentAccessRoleByIdRef.current[item.id];
          return snapshot?.generation === generation
            && resolveKnowledgeBasePermissions(
              snapshot.accessRole,
              snapshot.allowedOperations,
            ).canRead;
        });
        const acceptedIds = new Set(acceptedItems.map((item) => item.id));
        const newerItems = Array.from(currentById.values()).filter((item) => (
          !acceptedIds.has(item.id)
          && (currentAccessRoleByIdRef.current[item.id]?.generation ?? 0) > generation
        ));
        return [...acceptedItems, ...newerItems];
      });

      const usageResults = await Promise.allSettled(
        items
          .filter((item) => {
            const snapshot = currentAccessRoleByIdRef.current[item.id];
            return snapshot?.generation === generation
              && resolveKnowledgeBasePermissions(
                snapshot.accessRole,
                snapshot.allowedOperations,
              ).canRead;
          })
          .map(async (item) => ({
            kbId: item.id,
            usage: await knowledgeBaseApi.getKnowledgeBaseWorkspaceUsage(item.id),
          })),
      );

      const nextCounts: Record<string, number> = {};
      const nextUsage: Record<string, KnowledgeBaseWorkspaceUsageResponse> = {};
      usageResults.forEach((result) => {
        if (result.status !== 'fulfilled') {
          logger.warn('Failed to preload knowledge base workspace usage', { error: result.reason });
          return;
        }
        if (!resolveKnowledgeBasePermissions(
          currentAccessRoleByIdRef.current[result.value.kbId]?.accessRole,
          currentAccessRoleByIdRef.current[result.value.kbId]?.allowedOperations,
        ).canRead || (
          currentAccessRoleByIdRef.current[result.value.kbId]?.generation
          !== generation
        )) {
          return;
        }
        nextCounts[result.value.kbId] = result.value.usage.attachmentCount;
        nextUsage[result.value.kbId] = result.value.usage;
      });
      setAttachmentCounts((current) => {
        const next = { ...current };
        items.forEach((item) => {
          if (currentAccessRoleByIdRef.current[item.id]?.generation === generation) {
            delete next[item.id];
          }
        });
        Object.assign(next, nextCounts);
        return next;
      });
      setWorkspaceUsageById((current) => {
        const next = { ...current };
        items.forEach((item) => {
          if (currentAccessRoleByIdRef.current[item.id]?.generation === generation) {
            delete next[item.id];
          }
        });
        Object.assign(next, nextUsage);
        return next;
      });
    } catch (error) {
      logger.error('Failed to load knowledge bases', { error });
      setListError(t('knowledgeBase.list.loadFailed'));
    } finally {
      setIsLoadingKnowledgeBases(false);
    }
  }, [
    clearKnowledgeBaseResourceState,
    nextAuthorizationGeneration,
    t,
  ]);

  const createKnowledgeBase = useCallback(async (payload: KnowledgeBaseCreatePayload) => {
    setIsMutating(true);
    try {
      const created = await knowledgeBaseApi.createKnowledgeBase(payload);
      const permissions = resolveKnowledgeBasePermissions(
        created.accessRole,
        created.allowedOperations,
      );
      if (!permissions.canRead || !permissions.accessRole) {
        clearKnowledgeBaseResourceState(created.id);
        throw createKnowledgeBasePermissionError(
          t('common.authorization.accessDeniedDescription'),
        );
      }
      const normalizedCreated = {
        ...created,
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
      };
      const generation = nextAuthorizationGeneration();
      currentAccessRoleByIdRef.current[created.id] = {
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
        generation,
      };
      detailByIdRef.current[created.id] = normalizedCreated;
      setKnowledgeBases((current) => [
        normalizedCreated,
        ...current.filter((item) => item.id !== created.id),
      ]);
      setDetailById((current) => ({
        ...current,
        [created.id]: normalizedCreated,
      }));
      setAttachmentCounts((current) => ({ ...current, [created.id]: 0 }));
      setWorkspaceUsageById((current) => ({ ...current, [created.id]: EMPTY_USAGE }));
      setSharesById((current) => ({ ...current, [created.id]: [] }));
      return normalizedCreated;
    } finally {
      setIsMutating(false);
    }
  }, [
    clearKnowledgeBaseResourceState,
    nextAuthorizationGeneration,
    t,
  ]);

  const updateKnowledgeBase = useCallback(async (kbId: string, payload: KnowledgeBaseUpdatePayload) => {
    requireCurrentPermission(kbId, 'settings');
    setIsMutating(true);
    try {
      const updated = await knowledgeBaseApi.updateKnowledgeBase(kbId, payload);
      const permissions = resolveKnowledgeBasePermissions(
        updated.accessRole,
        updated.allowedOperations,
      );
      if (!permissions.canRead || !permissions.accessRole) {
        clearKnowledgeBaseResourceState(kbId);
        throw createKnowledgeBasePermissionError(
          t('common.authorization.accessDeniedDescription'),
        );
      }
      requireCurrentPermission(kbId, 'settings');
      const normalizedUpdated = {
        ...updated,
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
      };
      const generation = nextAuthorizationGeneration();
      currentAccessRoleByIdRef.current[kbId] = {
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
        generation,
      };
      detailByIdRef.current[kbId] = normalizedUpdated;
      setKnowledgeBases((current) => current.map((item) => (
        item.id === kbId ? normalizedUpdated : item
      )));
      setDetailById((current) => ({
        ...current,
        [kbId]: normalizedUpdated,
      }));
      return normalizedUpdated;
    } finally {
      setIsMutating(false);
    }
  }, [
    clearKnowledgeBaseResourceState,
    nextAuthorizationGeneration,
    requireCurrentPermission,
    t,
  ]);

  const updateKnowledgeBaseVisibility = useCallback(async (
    kbId: string,
    payload: KnowledgeBaseVisibilityUpdatePayload,
  ) => {
    requireCurrentPermission(kbId, 'visibility');
    setIsMutating(true);
    try {
      const updated = await knowledgeBaseApi.updateKnowledgeBaseVisibility(kbId, payload);
      requireCurrentPermission(kbId, 'visibility');
      const permissions = resolveKnowledgeBasePermissions(
        updated.accessRole,
        updated.allowedOperations,
      );
      if (!permissions.canRead || !permissions.accessRole) {
        clearKnowledgeBaseResourceState(kbId);
        throw createKnowledgeBasePermissionError(
          t('common.authorization.accessDeniedDescription'),
        );
      }
      const normalizedUpdated = {
        ...updated,
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
      };
      const generation = nextAuthorizationGeneration();
      currentAccessRoleByIdRef.current[kbId] = {
        accessRole: permissions.accessRole,
        allowedOperations: permissions.allowedOperations,
        generation,
      };
      detailByIdRef.current[kbId] = normalizedUpdated;
      setKnowledgeBases((current) => current.map((item) => (
        item.id === kbId ? normalizedUpdated : item
      )));
      setDetailById((current) => ({ ...current, [kbId]: normalizedUpdated }));
      return normalizedUpdated;
    } finally {
      setIsMutating(false);
    }
  }, [
    clearKnowledgeBaseResourceState,
    nextAuthorizationGeneration,
    requireCurrentPermission,
    t,
  ]);

  const deleteKnowledgeBase = useCallback(async (kbId: string, confirmationName: string) => {
    requireCurrentPermission(kbId, 'delete');
    setIsMutating(true);
    try {
      await knowledgeBaseApi.deleteKnowledgeBase(kbId, confirmationName);
      clearKnowledgeBaseResourceState(kbId);
    } finally {
      setIsMutating(false);
    }
  }, [clearKnowledgeBaseResourceState, requireCurrentPermission]);

  const createKnowledgeBaseShare = useCallback(async (kbId: string, payload: KnowledgeBaseShareCreatePayload) => {
    requireCurrentPermission(kbId, 'shares');
    setIsMutating(true);
    try {
      const created = await knowledgeBaseApi.createKnowledgeBaseShare(kbId, payload);
      requireCurrentPermission(kbId, 'shares');
      setSharesById((current) => ({ ...current, [kbId]: [...(current[kbId] ?? []), created] }));
      return created;
    } finally {
      setIsMutating(false);
    }
  }, [requireCurrentPermission]);

  const updateKnowledgeBaseShare = useCallback(async (
    kbId: string,
    shareId: string,
    payload: KnowledgeBaseShareUpdatePayload,
  ) => {
    requireCurrentPermission(kbId, 'shares');
    setIsMutating(true);
    try {
      const updated = await knowledgeBaseApi.updateKnowledgeBaseShare(kbId, shareId, payload);
      requireCurrentPermission(kbId, 'shares');
      setSharesById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).map((share) => (share.id === shareId ? updated : share)),
      }));
      return updated;
    } finally {
      setIsMutating(false);
    }
  }, [requireCurrentPermission]);

  const deleteKnowledgeBaseShare = useCallback(async (kbId: string, shareId: string) => {
    requireCurrentPermission(kbId, 'shares');
    setIsMutating(true);
    try {
      await knowledgeBaseApi.deleteKnowledgeBaseShare(kbId, shareId);
      requireCurrentPermission(kbId, 'shares');
      setSharesById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).filter((share) => share.id !== shareId),
      }));
    } finally {
      setIsMutating(false);
    }
  }, [requireCurrentPermission]);

  useEffect(() => {
    void reloadKnowledgeBases();
  }, [reloadKnowledgeBases]);

  const value = useMemo<KnowledgeBaseContextValue>(() => ({
    isReady: true,
    knowledgeBases,
    attachmentCounts,
    isLoadingKnowledgeBases,
    listError,
    detailById,
    sharesById,
    workspaceUsageById,
    isMutating,
    reloadKnowledgeBases,
    createKnowledgeBase,
    updateKnowledgeBase,
    updateKnowledgeBaseVisibility,
    deleteKnowledgeBase,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseWorkspaceUsage,
    createKnowledgeBaseShare,
    updateKnowledgeBaseShare,
    deleteKnowledgeBaseShare,
  }), [
    knowledgeBases,
    attachmentCounts,
    isLoadingKnowledgeBases,
    listError,
    detailById,
    sharesById,
    workspaceUsageById,
    isMutating,
    reloadKnowledgeBases,
    createKnowledgeBase,
    updateKnowledgeBase,
    updateKnowledgeBaseVisibility,
    deleteKnowledgeBase,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseWorkspaceUsage,
    createKnowledgeBaseShare,
    updateKnowledgeBaseShare,
    deleteKnowledgeBaseShare,
  ]);

  return (
    <KnowledgeBaseContext.Provider value={value}>
      {children}
    </KnowledgeBaseContext.Provider>
  );
};

export const useKnowledgeBase = (): KnowledgeBaseContextValue => {
  const context = useContext(KnowledgeBaseContext);
  if (!context) {
    throw new Error('useKnowledgeBase must be used within a KnowledgeBaseProvider');
  }
  return context;
};

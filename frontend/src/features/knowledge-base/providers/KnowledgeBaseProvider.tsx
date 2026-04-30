import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { useI18n } from '@/shared/hooks/useI18n';
import * as knowledgeBaseApi from '@/features/knowledge-base/api/knowledgeBaseApi';
import type {
  KnowledgeBaseAttachmentCreatePayload,
  KnowledgeBaseAttachmentSummary,
  KnowledgeBaseAttachmentUpdatePayload,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseDetail,
  KnowledgeBaseShareCreatePayload,
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareUpdatePayload,
  KnowledgeBaseSummary,
} from '@/shared/types/knowledgeBase';

export interface KnowledgeBaseProviderProps {
  children: React.ReactNode;
}

export interface KnowledgeBaseContextValue {
  isReady: boolean;
  knowledgeBases: KnowledgeBaseSummary[];
  attachmentCounts: Record<string, number>;
  isLoadingKnowledgeBases: boolean;
  listError: string | null;
  detailById: Record<string, KnowledgeBaseDetail | undefined>;
  sharesById: Record<string, KnowledgeBaseShareSummary[] | undefined>;
  attachmentsById: Record<string, KnowledgeBaseAttachmentSummary[] | undefined>;
  isMutating: boolean;
  reloadKnowledgeBases: () => Promise<void>;
  createKnowledgeBase: (payload: KnowledgeBaseCreatePayload) => Promise<KnowledgeBaseDetail>;
  loadKnowledgeBaseDetail: (kbId: string) => Promise<KnowledgeBaseDetail>;
  loadKnowledgeBaseShares: (kbId: string) => Promise<KnowledgeBaseShareSummary[]>;
  loadKnowledgeBaseAttachments: (kbId: string) => Promise<KnowledgeBaseAttachmentSummary[]>;
  createKnowledgeBaseShare: (kbId: string, payload: KnowledgeBaseShareCreatePayload) => Promise<KnowledgeBaseShareSummary>;
  updateKnowledgeBaseShare: (kbId: string, shareId: string, payload: KnowledgeBaseShareUpdatePayload) => Promise<KnowledgeBaseShareSummary>;
  deleteKnowledgeBaseShare: (kbId: string, shareId: string) => Promise<void>;
  createKnowledgeBaseAttachment: (kbId: string, payload: KnowledgeBaseAttachmentCreatePayload) => Promise<KnowledgeBaseAttachmentSummary>;
  updateKnowledgeBaseAttachment: (kbId: string, attachmentId: string, payload: KnowledgeBaseAttachmentUpdatePayload) => Promise<KnowledgeBaseAttachmentSummary>;
  deleteKnowledgeBaseAttachment: (kbId: string, attachmentId: string) => Promise<void>;
}

const KnowledgeBaseContext = createContext<KnowledgeBaseContextValue | undefined>(undefined);
const logger = createLogger('KnowledgeBaseProvider');

export const KnowledgeBaseProvider: React.FC<KnowledgeBaseProviderProps> = ({ children }) => {
  const { t } = useI18n();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [attachmentCounts, setAttachmentCounts] = useState<Record<string, number>>({});
  const [detailById, setDetailById] = useState<Record<string, KnowledgeBaseDetail | undefined>>({});
  const [sharesById, setSharesById] = useState<Record<string, KnowledgeBaseShareSummary[] | undefined>>({});
  const [attachmentsById, setAttachmentsById] = useState<Record<string, KnowledgeBaseAttachmentSummary[] | undefined>>({});
  const [isLoadingKnowledgeBases, setIsLoadingKnowledgeBases] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  const loadKnowledgeBaseAttachments = useCallback(async (kbId: string) => {
    const items = await knowledgeBaseApi.listKnowledgeBaseAttachments(kbId);
    setAttachmentsById((current) => ({ ...current, [kbId]: items }));
    setAttachmentCounts((current) => ({ ...current, [kbId]: items.length }));
    return items;
  }, []);

  const loadKnowledgeBaseShares = useCallback(async (kbId: string) => {
    const items = await knowledgeBaseApi.listKnowledgeBaseShares(kbId);
    setSharesById((current) => ({ ...current, [kbId]: items }));
    return items;
  }, []);

  const loadKnowledgeBaseDetail = useCallback(async (kbId: string) => {
    const detail = await knowledgeBaseApi.getKnowledgeBase(kbId);
    setDetailById((current) => ({ ...current, [kbId]: detail }));
    setKnowledgeBases((current) => current.map((item) => (item.id === kbId ? detail : item)));
    return detail;
  }, []);

  const reloadKnowledgeBases = useCallback(async () => {
    setIsLoadingKnowledgeBases(true);
    setListError(null);
    try {
      const items = await knowledgeBaseApi.listKnowledgeBases();
      setKnowledgeBases(items);

      const attachmentResults = await Promise.allSettled(
        items.map(async (item) => {
          const attachments = await knowledgeBaseApi.listKnowledgeBaseAttachments(item.id);
          return { kbId: item.id, count: attachments.length, attachments };
        }),
      );

      const nextCounts: Record<string, number> = {};
      const nextAttachments: Record<string, KnowledgeBaseAttachmentSummary[]> = {};
      attachmentResults.forEach((result) => {
        if (result.status !== 'fulfilled') {
          logger.warn('Failed to preload knowledge base attachments', { error: result.reason });
          return;
        }
        nextCounts[result.value.kbId] = result.value.count;
        nextAttachments[result.value.kbId] = result.value.attachments;
      });
      setAttachmentCounts(nextCounts);
      setAttachmentsById((current) => ({ ...current, ...nextAttachments }));
    } catch (error) {
      logger.error('Failed to load knowledge bases', { error });
      setListError(error instanceof Error ? error.message : t('knowledgeBase.list.loadFailed'));
    } finally {
      setIsLoadingKnowledgeBases(false);
    }
  }, []);

  const createKnowledgeBase = useCallback(async (payload: KnowledgeBaseCreatePayload) => {
    setIsMutating(true);
    try {
      const created = await knowledgeBaseApi.createKnowledgeBase(payload);
      setKnowledgeBases((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setDetailById((current) => ({ ...current, [created.id]: created }));
      setAttachmentCounts((current) => ({ ...current, [created.id]: 0 }));
      setAttachmentsById((current) => ({ ...current, [created.id]: [] }));
      setSharesById((current) => ({ ...current, [created.id]: [] }));
      return created;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const createKnowledgeBaseShare = useCallback(async (
    kbId: string,
    payload: KnowledgeBaseShareCreatePayload,
  ) => {
    setIsMutating(true);
    try {
      const created = await knowledgeBaseApi.createKnowledgeBaseShare(kbId, payload);
      setSharesById((current) => ({
        ...current,
        [kbId]: [...(current[kbId] ?? []), created],
      }));
      return created;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const updateKnowledgeBaseShare = useCallback(async (
    kbId: string,
    shareId: string,
    payload: KnowledgeBaseShareUpdatePayload,
  ) => {
    setIsMutating(true);
    try {
      const updated = await knowledgeBaseApi.updateKnowledgeBaseShare(kbId, shareId, payload);
      setSharesById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).map((share) => (share.id === shareId ? updated : share)),
      }));
      return updated;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const deleteKnowledgeBaseShare = useCallback(async (kbId: string, shareId: string) => {
    setIsMutating(true);
    try {
      await knowledgeBaseApi.deleteKnowledgeBaseShare(kbId, shareId);
      setSharesById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).filter((share) => share.id !== shareId),
      }));
    } finally {
      setIsMutating(false);
    }
  }, []);

  const createKnowledgeBaseAttachment = useCallback(async (
    kbId: string,
    payload: KnowledgeBaseAttachmentCreatePayload,
  ) => {
    setIsMutating(true);
    try {
      const created = await knowledgeBaseApi.createKnowledgeBaseAttachment(kbId, payload);
      setAttachmentsById((current) => ({
        ...current,
        [kbId]: [...(current[kbId] ?? []), created],
      }));
      setAttachmentCounts((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? 0) + 1,
      }));
      return created;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const updateKnowledgeBaseAttachment = useCallback(async (
    kbId: string,
    attachmentId: string,
    payload: KnowledgeBaseAttachmentUpdatePayload,
  ) => {
    setIsMutating(true);
    try {
      const updated = await knowledgeBaseApi.updateKnowledgeBaseAttachment(kbId, attachmentId, payload);
      setAttachmentsById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).map((attachment) => (
          attachment.id === attachmentId ? updated : attachment
        )),
      }));
      return updated;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const deleteKnowledgeBaseAttachment = useCallback(async (kbId: string, attachmentId: string) => {
    setIsMutating(true);
    try {
      await knowledgeBaseApi.deleteKnowledgeBaseAttachment(kbId, attachmentId);
      setAttachmentsById((current) => ({
        ...current,
        [kbId]: (current[kbId] ?? []).filter((attachment) => attachment.id !== attachmentId),
      }));
      setAttachmentCounts((current) => ({
        ...current,
        [kbId]: Math.max(0, (current[kbId] ?? 1) - 1),
      }));
    } finally {
      setIsMutating(false);
    }
  }, []);

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
    attachmentsById,
    isMutating,
    reloadKnowledgeBases,
    createKnowledgeBase,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseAttachments,
    createKnowledgeBaseShare,
    updateKnowledgeBaseShare,
    deleteKnowledgeBaseShare,
    createKnowledgeBaseAttachment,
    updateKnowledgeBaseAttachment,
    deleteKnowledgeBaseAttachment,
  }), [
    knowledgeBases,
    attachmentCounts,
    isLoadingKnowledgeBases,
    listError,
    detailById,
    sharesById,
    attachmentsById,
    isMutating,
    reloadKnowledgeBases,
    createKnowledgeBase,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseAttachments,
    createKnowledgeBaseShare,
    updateKnowledgeBaseShare,
    deleteKnowledgeBaseShare,
    createKnowledgeBaseAttachment,
    updateKnowledgeBaseAttachment,
    deleteKnowledgeBaseAttachment,
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

export default KnowledgeBaseProvider;

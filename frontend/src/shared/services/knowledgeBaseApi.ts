import { apiClient } from '@/shared/api/apiClient';
import type {
  KnowledgeBaseAttachmentListResponse,
  KnowledgeBaseAttachmentCreatePayload,
  KnowledgeBaseAttachmentSummary,
  KnowledgeBaseAttachmentUpdatePayload,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseDetail,
  KnowledgeBaseListResponse,
  KnowledgeBaseShareCreatePayload,
  KnowledgeBaseShareListResponse,
  KnowledgeBaseSummary,
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareUpdatePayload,
  KnowledgeBaseUpdatePayload,
} from '@/shared/types/knowledgeBase';

export async function listKnowledgeBases(): Promise<KnowledgeBaseSummary[]> {
  const response = await apiClient.get<KnowledgeBaseListResponse>('/knowledge-bases');
  return response.items ?? [];
}

export async function getKnowledgeBase(kbId: string): Promise<KnowledgeBaseDetail> {
  return apiClient.get<KnowledgeBaseDetail>(`/knowledge-bases/${kbId}`);
}

export async function createKnowledgeBase(payload: KnowledgeBaseCreatePayload): Promise<KnowledgeBaseDetail> {
  return apiClient.post<KnowledgeBaseDetail>('/knowledge-bases', payload);
}

export async function updateKnowledgeBase(
  kbId: string,
  payload: KnowledgeBaseUpdatePayload,
): Promise<KnowledgeBaseDetail> {
  return apiClient.patch<KnowledgeBaseDetail>(`/knowledge-bases/${kbId}`, payload);
}

export async function deleteKnowledgeBase(kbId: string, force = false): Promise<KnowledgeBaseDetail> {
  const query = force ? '?force=true' : '';
  return apiClient.delete<KnowledgeBaseDetail>(`/knowledge-bases/${kbId}${query}`);
}

export async function listKnowledgeBaseShares(kbId: string) {
  const response = await apiClient.get<KnowledgeBaseShareListResponse>(`/knowledge-bases/${kbId}/shares`);
  return response.items ?? [];
}

export async function createKnowledgeBaseShare(
  kbId: string,
  payload: KnowledgeBaseShareCreatePayload,
): Promise<KnowledgeBaseShareSummary> {
  return apiClient.post<KnowledgeBaseShareSummary>(`/knowledge-bases/${kbId}/shares`, payload);
}

export async function updateKnowledgeBaseShare(
  kbId: string,
  shareId: string,
  payload: KnowledgeBaseShareUpdatePayload,
): Promise<KnowledgeBaseShareSummary> {
  return apiClient.patch<KnowledgeBaseShareSummary>(`/knowledge-bases/${kbId}/shares/${shareId}`, payload);
}

export async function deleteKnowledgeBaseShare(kbId: string, shareId: string): Promise<void> {
  return apiClient.delete<void>(`/knowledge-bases/${kbId}/shares/${shareId}`);
}

export async function listKnowledgeBaseAttachments(kbId: string) {
  const response = await apiClient.get<KnowledgeBaseAttachmentListResponse>(`/knowledge-bases/${kbId}/attachments`);
  return response.items ?? [];
}

export async function createKnowledgeBaseAttachment(
  kbId: string,
  payload: KnowledgeBaseAttachmentCreatePayload,
): Promise<KnowledgeBaseAttachmentSummary> {
  return apiClient.post<KnowledgeBaseAttachmentSummary>(`/knowledge-bases/${kbId}/attachments`, payload);
}

export async function updateKnowledgeBaseAttachment(
  kbId: string,
  attachmentId: string,
  payload: KnowledgeBaseAttachmentUpdatePayload,
): Promise<KnowledgeBaseAttachmentSummary> {
  return apiClient.patch<KnowledgeBaseAttachmentSummary>(`/knowledge-bases/${kbId}/attachments/${attachmentId}`, payload);
}

export async function deleteKnowledgeBaseAttachment(kbId: string, attachmentId: string): Promise<void> {
  return apiClient.delete<void>(`/knowledge-bases/${kbId}/attachments/${attachmentId}`);
}

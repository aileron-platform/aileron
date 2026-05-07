import { apiClient } from '@/shared/api/apiClient';
import type {
  VersionControlBranch,
  VersionControlBlobResponse,
  VersionControlChangesResponse,
  VersionControlCommitFilesResponse,
  VersionControlCommitListResponse,
  VersionControlDiffResponse,
  VersionControlStatus,
} from '@/shared/types/versionControl';
import type {
  KnowledgeBaseAttachmentListResponse,
  KnowledgeBaseAttachmentCreatePayload,
  KnowledgeBaseAttachmentSummary,
  KnowledgeBaseAttachmentUpdatePayload,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseDetail,
  KnowledgeBaseGitEnablePayload,
  KnowledgeBaseGitLfsEnablePayload,
  KnowledgeBaseGitRepositoryStatus,
  KnowledgeBaseGraphResponse,
  KnowledgeBaseIngestJobResponse,
  KnowledgeBaseListResponse,
  KnowledgeBaseLintReportResponse,
  KnowledgeBaseShareCreatePayload,
  KnowledgeBaseShareListResponse,
  KnowledgeBaseSummary,
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareUpdatePayload,
  KnowledgeBaseReviewItem,
  KnowledgeBaseReviewItemListResponse,
  KnowledgeBaseTemplateListResponse,
  KnowledgeBaseTemplateMetadata,
  KnowledgeBaseUpdatePayload,
  KnowledgeBaseVersionControlStatus,
  KnowledgeBaseWikiPageResponse,
  KnowledgeBaseWikiPagesResponse,
} from '@/shared/types/knowledgeBase';

interface KnowledgeBaseCheckoutRequest {
  create?: boolean;
  startPoint?: string;
  stash?: boolean;
}

interface KnowledgeBaseRemoteRequest {
  remote?: string;
  branch?: string;
}

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

export async function getKnowledgeBaseGraph(kbId: string): Promise<KnowledgeBaseGraphResponse> {
  return apiClient.get<KnowledgeBaseGraphResponse>(`/knowledge-bases/${kbId}/graph`);
}

export async function listKnowledgeBaseWikiPages(kbId: string): Promise<KnowledgeBaseWikiPagesResponse> {
  return apiClient.get<KnowledgeBaseWikiPagesResponse>(`/knowledge-bases/${kbId}/wiki/pages`);
}

export async function getKnowledgeBaseWikiPage(kbId: string, path: string): Promise<KnowledgeBaseWikiPageResponse> {
  return apiClient.get<KnowledgeBaseWikiPageResponse>(
    `/knowledge-bases/${kbId}/wiki/page?path=${encodeURIComponent(path)}`,
  );
}

export async function runKnowledgeBaseLint(kbId: string): Promise<KnowledgeBaseLintReportResponse> {
  return apiClient.post<KnowledgeBaseLintReportResponse>(`/knowledge-bases/${kbId}/lint`, {});
}

export async function createKnowledgeBaseIngestJob(kbId: string): Promise<KnowledgeBaseIngestJobResponse> {
  return apiClient.post<KnowledgeBaseIngestJobResponse>(`/knowledge-bases/${kbId}/ingest`, {});
}

export async function getKnowledgeBaseGitRepositoryStatus(kbId: string): Promise<KnowledgeBaseGitRepositoryStatus> {
  return apiClient.get<KnowledgeBaseGitRepositoryStatus>(`/knowledge-bases/${kbId}/git/repository/status`);
}

export async function enableKnowledgeBaseGitRepository(
  kbId: string,
  payload: KnowledgeBaseGitEnablePayload = {},
): Promise<KnowledgeBaseGitRepositoryStatus> {
  return apiClient.post<KnowledgeBaseGitRepositoryStatus>(`/knowledge-bases/${kbId}/git/repository/enable`, payload);
}

export async function enableKnowledgeBaseGitLfs(
  kbId: string,
  payload: KnowledgeBaseGitLfsEnablePayload = {},
): Promise<{ success: boolean; message: string }> {
  return apiClient.post<{ success: boolean; message: string }>(`/knowledge-bases/${kbId}/git/lfs/enable`, payload);
}

export async function getKnowledgeBaseVersionControlStatus(kbId: string): Promise<KnowledgeBaseVersionControlStatus> {
  return apiClient.get<KnowledgeBaseVersionControlStatus>(`/knowledge-bases/${kbId}/git/version-control/status`);
}

const knowledgeBaseVersionControlBase = (kbId: string) => `/knowledge-bases/${kbId}/git/version-control`;

export const knowledgeBaseVersionControlApi = {
  getStatus: (kbId: string) =>
    apiClient.get<VersionControlStatus>(`${knowledgeBaseVersionControlBase(kbId)}/status`),
  getChanges: (kbId: string, page = 1, pageSize = 100) =>
    apiClient.get<VersionControlChangesResponse>(
      `${knowledgeBaseVersionControlBase(kbId)}/changes?page=${page}&pageSize=${pageSize}`,
    ),
  getBranches: async (kbId: string) => {
    const response = await apiClient.get<{ branches: VersionControlBranch[] }>(
      `${knowledgeBaseVersionControlBase(kbId)}/branches`,
    );
    return response.branches ?? [];
  },
  checkoutBranch: (kbId: string, branch: string, payload: KnowledgeBaseCheckoutRequest) =>
    apiClient.post<{ branch: string; created: boolean; stashedChanges?: string | null }>(
      `${knowledgeBaseVersionControlBase(kbId)}/branches/${encodeURIComponent(branch)}/checkout`,
      payload,
    ),
  stage: (kbId: string, paths: string[]) =>
    apiClient.post<{ staged: string[]; unstaged: string[] }>(`${knowledgeBaseVersionControlBase(kbId)}/stage`, {
      paths,
      includeUntracked: true,
    }),
  unstage: (kbId: string, paths: string[]) =>
    apiClient.post<{ unstaged: string[]; remainingStaged: number }>(
      `${knowledgeBaseVersionControlBase(kbId)}/unstage`,
      { paths },
    ),
  discard: (kbId: string, paths: string[]) =>
    apiClient.post<{ discarded: string[]; warnings: string[] }>(
      `${knowledgeBaseVersionControlBase(kbId)}/discard`,
      { paths },
    ),
  commit: (kbId: string, message: string, paths?: string[]) =>
    apiClient.post<{ commit: unknown }>(`${knowledgeBaseVersionControlBase(kbId)}/commit`, { message, paths }),
  getCommits: (kbId: string, page = 1, pageSize = 20, branch?: string) => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('pageSize', String(pageSize));
    if (branch) params.set('branch', branch);
    return apiClient.get<VersionControlCommitListResponse>(`${knowledgeBaseVersionControlBase(kbId)}/commits?${params}`);
  },
  getCommitFiles: (kbId: string, commitId: string) =>
    apiClient.get<VersionControlCommitFilesResponse>(
      `${knowledgeBaseVersionControlBase(kbId)}/commits/${encodeURIComponent(commitId)}/files`,
    ),
  getDiff: (kbId: string, path: string, head: 'INDEX' | 'WORKTREE' = 'WORKTREE') =>
    apiClient.get<VersionControlDiffResponse>(
      `${knowledgeBaseVersionControlBase(kbId)}/diff?path=${encodeURIComponent(path)}&head=${encodeURIComponent(head)}`,
    ),
  getBlob: (kbId: string, path: string, revision?: string | null) => {
    const params = new URLSearchParams();
    params.set('path', path);
    if (revision) {
      params.set('revision', revision);
    }
    return apiClient.get<VersionControlBlobResponse>(`${knowledgeBaseVersionControlBase(kbId)}/blob?${params}`);
  },
  fetch: (kbId: string, payload: KnowledgeBaseRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(
      `${knowledgeBaseVersionControlBase(kbId)}/fetch`,
      payload,
    ),
  pull: (kbId: string, payload: KnowledgeBaseRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(
      `${knowledgeBaseVersionControlBase(kbId)}/pull`,
      payload,
    ),
  push: (kbId: string, payload: KnowledgeBaseRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(
      `${knowledgeBaseVersionControlBase(kbId)}/push`,
      payload,
    ),
  setRemoteUrl: (kbId: string, remoteUrl: string) =>
    apiClient.post<{ success: boolean; message: string }>(`/knowledge-bases/${kbId}/git/remote-url`, { remoteUrl }),
  revert: (kbId: string, commitId: string) =>
    apiClient.post<{ success: boolean; message: string }>(
      `${knowledgeBaseVersionControlBase(kbId)}/revert`,
      { commitId },
    ),
  rollback: (kbId: string, revision: string, confirm: string) =>
    apiClient.post<{ success: boolean; message: string }>(
      `${knowledgeBaseVersionControlBase(kbId)}/rollback`,
      { revision, confirm },
    ),
};

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

export async function listKnowledgeBaseTemplates(): Promise<KnowledgeBaseTemplateMetadata[]> {
  const response = await apiClient.get<KnowledgeBaseTemplateListResponse>('/knowledge-bases/templates');
  return response.items ?? [];
}

export async function listKnowledgeBaseReviews(
  kbId: string,
  status?: 'open' | 'resolved' | 'dismissed',
): Promise<KnowledgeBaseReviewItemListResponse> {
  const params = status ? `?status=${status}` : '';
  return apiClient.get<KnowledgeBaseReviewItemListResponse>(`/knowledge-bases/${kbId}/reviews${params}`);
}

export async function resolveKnowledgeBaseReview(kbId: string, itemId: string): Promise<KnowledgeBaseReviewItem> {
  return apiClient.patch<KnowledgeBaseReviewItem>(`/knowledge-bases/${kbId}/reviews/${itemId}`, { status: 'resolved' });
}

export async function dismissKnowledgeBaseReview(kbId: string, itemId: string): Promise<KnowledgeBaseReviewItem> {
  return apiClient.patch<KnowledgeBaseReviewItem>(`/knowledge-bases/${kbId}/reviews/${itemId}`, { status: 'dismissed' });
}

export async function convertKnowledgeBaseReview(
  kbId: string,
  itemId: string,
  payload: { title: string; slug?: string },
): Promise<KnowledgeBaseReviewItem> {
  return apiClient.post<KnowledgeBaseReviewItem>(`/knowledge-bases/${kbId}/reviews/${itemId}/convert`, payload);
}

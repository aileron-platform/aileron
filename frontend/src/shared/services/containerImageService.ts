/**
 * 容器映像服務
 *
 * 提供容器映像配置的查詢功能
 */

import { apiClient } from '../api/apiClient';
import type { ContainerImage, ContainerImagesResponse } from '../types/containerImage';

/**
 * 取得所有可用的容器映像
 */
export async function getContainerImages(activeOnly: boolean = true): Promise<ContainerImagesResponse> {
  const params = new URLSearchParams();

  if (activeOnly !== undefined) {
    params.append('active_only', String(activeOnly));
  }

  const url = params.toString() ? `/container-images?${params.toString()}` : '/container-images';

  return apiClient.get<ContainerImagesResponse>(url);
}

/**
 * 根據 ID 取得容器映像詳情
 */
export async function getContainerImageById(imageId: string): Promise<ContainerImage> {
  return apiClient.get<ContainerImage>(`/container-images/${imageId}`);
}

/**
 * 重新載入容器映像配置
 */
export async function reloadContainerImages(): Promise<void> {
  await apiClient.post<void>('/container-images/reload', {});
}


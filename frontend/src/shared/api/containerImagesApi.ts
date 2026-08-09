import { apiClient } from './apiClient';
import type { ContainerImagesResponse } from '../types/containerImage';

export async function getContainerImages(activeOnly: boolean = true): Promise<ContainerImagesResponse> {
  const params = new URLSearchParams();

  if (activeOnly !== undefined) {
    params.append('active_only', String(activeOnly));
  }

  const url = params.toString() ? `/container-images?${params.toString()}` : '/container-images';

  return apiClient.get<ContainerImagesResponse>(url);
}

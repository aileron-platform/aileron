/**
 * 容器映像 Hook
 * 
 * 提供容器映像配置的查詢功能
 */

import { useQuery } from '@tanstack/react-query';
import { getContainerImages } from '../services/containerImageService';
import type { ContainerImagesResponse } from '../types/containerImage';

/**
 * 使用容器映像列表
 */
export function useContainerImages(activeOnly: boolean = true) {
  return useQuery<ContainerImagesResponse>({
    queryKey: ['container-images', activeOnly],
    queryFn: () => getContainerImages(activeOnly),
    staleTime: 5 * 60 * 1000, // 5 分鐘
    gcTime: 10 * 60 * 1000, // 10 分鐘
  });
}


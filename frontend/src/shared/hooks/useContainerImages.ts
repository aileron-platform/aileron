/**
 * 
 */

import { useQuery } from '@tanstack/react-query';
import { getContainerImages } from '../api/containerImagesApi';
import type { ContainerImagesResponse } from '../types/containerImage';

/**
 */
export function useContainerImages(activeOnly: boolean = true) {
  return useQuery<ContainerImagesResponse>({
    queryKey: ['container-images', activeOnly],
    queryFn: () => getContainerImages(activeOnly),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

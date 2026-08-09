import { ApiError } from '@/shared/api/apiClient';

export const isVersionControlNotInitializedError = (error: unknown): error is ApiError => {
  return error instanceof ApiError && error.errorCode === 'repository_not_initialized';
};

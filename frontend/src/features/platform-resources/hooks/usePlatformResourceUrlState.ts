import React from 'react';
import { useSearchParams } from 'react-router-dom';
import type {
  PlatformResourceCapacityRisk,
  PlatformResourceListQuery,
  PlatformResourceRange,
} from '../model/platformResourceTypes';

const RANGES: PlatformResourceRange[] = ['7d', '30d', '90d'];
const RISKS: PlatformResourceCapacityRisk[] = ['normal', 'warning', 'critical', 'unknown', 'stale'];
const SORTS: NonNullable<PlatformResourceListQuery['sort']>[] = [
  'name', 'created_at', 'used_bytes', 'utilization',
];

const valueFrom = <T extends string>(value: string | null, values: readonly T[]): T | undefined => (
  value && values.includes(value as T) ? value as T : undefined
);

export const usePlatformResourceUrlState = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const parsedPage = Number(searchParams.get('page'));
  const page = Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const range = valueFrom(searchParams.get('range'), RANGES) ?? '30d';
  const sort = valueFrom(searchParams.get('sort'), SORTS);
  const order = valueFrom(searchParams.get('order'), ['asc', 'desc'] as const);
  const capacityRisk = valueFrom(searchParams.get('capacityRisk'), RISKS);

  const update = React.useCallback((updates: Record<string, string | null>) => {
    setSearchParams(current => {
      const next = new URLSearchParams(current);
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) next.delete(key);
        else next.set(key, value);
      });
      return next;
    });
  }, [setSearchParams]);

  return {
    searchParams,
    range,
    query: searchParams.get('q') ?? '',
    page,
    health: searchParams.get('health') || undefined,
    visibility: searchParams.get('visibility') || undefined,
    indexingHealth: searchParams.get('indexingHealth') || undefined,
    capacityRisk,
    sort,
    order,
    update,
  };
};

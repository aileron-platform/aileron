import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AutomationJob } from '../model/automationTypes';

const JOBS_PER_PAGE = 6;

export const useAutomationJobPagination = (
  jobs: AutomationJob[],
  resetKey: string,
) => {
  const [page, setPage] = useState(1);
  const totalItems = jobs.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / JOBS_PER_PAGE));

  useEffect(() => {
    setPage(1);
  }, [resetKey]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const paginatedJobs = useMemo(() => {
    const start = (page - 1) * JOBS_PER_PAGE;
    return jobs.slice(start, start + JOBS_PER_PAGE);
  }, [jobs, page]);

  const onPageChange = useCallback((nextPage: number) => {
    setPage(Math.min(Math.max(nextPage, 1), totalPages));
  }, [totalPages]);

  return {
    page,
    totalPages,
    totalItems,
    pageSize: JOBS_PER_PAGE,
    paginatedJobs,
    onPageChange,
  };
};

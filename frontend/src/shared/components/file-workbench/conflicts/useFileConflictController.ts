import { useCallback, useEffect, useRef, useState } from 'react';
import {
  buildFileConflictResolutions,
  canApplyFileConflictStrategy,
  canApplyFileConflictStrategyToAll,
  type FileConflictItemStrategies,
} from './fileConflictModel';
import type {
  FileConflictBatchResult,
  FileConflictControllerPhase,
  FileConflictExecutionRequest,
  FileConflictItem,
  FileConflictPreflightRequest,
  FileConflictStrategy,
  FileConflictWorkflowTransport,
  ResolvableFileConflictStrategy,
} from './types';

export interface UseFileConflictControllerOptions<TPayload> {
  transport: FileConflictWorkflowTransport<TPayload>;
  onCompleted?: (result: FileConflictBatchResult) => void;
  onCancelled?: () => void;
  onError?: (error: unknown, stage: 'preflight' | 'execute') => void;
}

interface ActiveFileConflictBatch<TPayload> {
  request: FileConflictPreflightRequest;
  payload: TPayload;
}

const isAbortError = (error: unknown): boolean => (
  error instanceof DOMException && error.name === 'AbortError'
);

export const useFileConflictController = <TPayload,>({
  transport,
  onCompleted,
  onCancelled,
  onError,
}: UseFileConflictControllerOptions<TPayload>) => {
  const requestSequenceRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeBatchRef = useRef<ActiveFileConflictBatch<TPayload> | null>(null);
  const [phase, setPhase] = useState<FileConflictControllerPhase>('idle');
  const [conflicts, setConflicts] = useState<FileConflictItem[]>([]);
  const [defaultStrategy, setDefaultStrategyState] = useState<ResolvableFileConflictStrategy>('keep-both');
  const [itemStrategies, setItemStrategies] = useState<FileConflictItemStrategies>({});
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<FileConflictBatchResult | null>(null);

  const beginRequest = useCallback(() => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    requestSequenceRef.current += 1;
    return { controller, requestId: requestSequenceRef.current };
  }, []);

  const isCurrentRequest = useCallback((requestId: number) => (
    requestSequenceRef.current === requestId
  ), []);

  const executeBatch = useCallback(async (
    batch: ActiveFileConflictBatch<TPayload>,
    executionConflicts: FileConflictItem[],
    executionDefaultStrategy: FileConflictStrategy,
    executionItemStrategies: FileConflictItemStrategies,
    requestId: number,
    controller: AbortController,
  ): Promise<FileConflictBatchResult | null> => {
    setPhase('executing');
    setError(null);
    const executionRequest: FileConflictExecutionRequest<TPayload> = {
      ...batch.request,
      defaultStrategy: executionDefaultStrategy,
      resolutions: executionConflicts.length === 0
        ? []
        : buildFileConflictResolutions(
            executionConflicts,
            executionDefaultStrategy as ResolvableFileConflictStrategy,
            executionItemStrategies,
          ),
      payload: batch.payload,
    };

    try {
      const nextResult = await transport.execute(executionRequest, { signal: controller.signal });
      if (!isCurrentRequest(requestId)) return null;
      setResult(nextResult);
      setPhase('completed');
      activeBatchRef.current = null;
      onCompleted?.(nextResult);
      return nextResult;
    } catch (executionError) {
      if (!isCurrentRequest(requestId) || isAbortError(executionError)) return null;
      setError(executionError);
      setPhase(executionConflicts.length > 0 ? 'resolving' : 'preflight-error');
      onError?.(executionError, 'execute');
      return null;
    }
  }, [isCurrentRequest, onCompleted, onError, transport]);

  const start = useCallback(async (
    request: FileConflictPreflightRequest,
    payload: TPayload,
  ): Promise<FileConflictBatchResult | null> => {
    const { controller, requestId } = beginRequest();
    const batch = { request, payload };
    activeBatchRef.current = batch;
    setPhase('preflighting');
    setConflicts([]);
    setDefaultStrategyState('keep-both');
    setItemStrategies({});
    setError(null);
    setResult(null);

    try {
      const preflight = await transport.preflight(request, { signal: controller.signal });
      if (!isCurrentRequest(requestId)) return null;
      setConflicts(preflight.conflicts);
      if (preflight.conflicts.length > 0) {
        setPhase('resolving');
        return null;
      }
      return executeBatch(batch, [], 'cancel', {}, requestId, controller);
    } catch (preflightError) {
      if (!isCurrentRequest(requestId) || isAbortError(preflightError)) return null;
      setError(preflightError);
      setPhase('preflight-error');
      onError?.(preflightError, 'preflight');
      return null;
    }
  }, [beginRequest, executeBatch, isCurrentRequest, onError, transport]);

  const setDefaultStrategy = useCallback((strategy: ResolvableFileConflictStrategy) => {
    if (!canApplyFileConflictStrategyToAll(conflicts, strategy)) return;
    setDefaultStrategyState(strategy);
    setItemStrategies({});
  }, [conflicts]);

  const setItemStrategy = useCallback((
    sourcePath: string,
    strategy: ResolvableFileConflictStrategy,
  ) => {
    const conflict = conflicts.find((item) => item.sourcePath === sourcePath);
    if (!conflict || !canApplyFileConflictStrategy(conflict, strategy)) return;
    setItemStrategies((current) => ({ ...current, [sourcePath]: strategy }));
  }, [conflicts]);

  const confirm = useCallback(async (): Promise<FileConflictBatchResult | null> => {
    const batch = activeBatchRef.current;
    if (!batch || phase !== 'resolving') return null;
    const { controller, requestId } = beginRequest();
    activeBatchRef.current = batch;
    return executeBatch(
      batch,
      conflicts,
      defaultStrategy,
      itemStrategies,
      requestId,
      controller,
    );
  }, [beginRequest, conflicts, defaultStrategy, executeBatch, itemStrategies, phase]);

  const cancel = useCallback(() => {
    if (phase === 'executing') return;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    requestSequenceRef.current += 1;
    activeBatchRef.current = null;
    setPhase('cancelled');
    setError(null);
    onCancelled?.();
  }, [onCancelled, phase]);

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    requestSequenceRef.current += 1;
    activeBatchRef.current = null;
    setPhase('idle');
    setConflicts([]);
    setDefaultStrategyState('keep-both');
    setItemStrategies({});
    setError(null);
    setResult(null);
  }, []);

  useEffect(() => () => {
    abortControllerRef.current?.abort();
    requestSequenceRef.current += 1;
  }, []);

  return {
    phase,
    open: phase === 'resolving',
    pending: phase === 'preflighting' || phase === 'executing',
    operation: activeBatchRef.current?.request.operation ?? null,
    conflicts,
    defaultStrategy,
    itemStrategies,
    error,
    result,
    start,
    setDefaultStrategy,
    setItemStrategy,
    confirm,
    cancel,
    reset,
  };
};

export type FileConflictController<TPayload> = ReturnType<
  typeof useFileConflictController<TPayload>
>;

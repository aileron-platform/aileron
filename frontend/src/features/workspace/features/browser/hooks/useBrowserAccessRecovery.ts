import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/shared/api/apiClient';
import type { BrowserAccessResponse } from '../../../api/workspaceLifecycleApi';
import type { NekoConnectionState } from '../lib/nekoProtocol';

const MAX_ATTEMPTS = 5;
const RECOVERY_BUDGET_MS = 120_000;
const MAX_DELAY_MS = 30_000;

type RecoveryState = 'idle' | 'requesting' | 'recovering' | 'connected' | 'exhausted';

interface UseBrowserAccessRecoveryOptions {
  workspaceId: string | null;
  enabled: boolean;
  connectionState: NekoConnectionState;
  requestAccess: (workspaceId: string) => Promise<BrowserAccessResponse>;
}

interface UseBrowserAccessRecoveryResult {
  access: BrowserAccessResponse | null;
  generation: number;
  state: RecoveryState;
  errorKey: string | null;
  retry: () => void;
}

export function useBrowserAccessRecovery({
  workspaceId,
  enabled,
  connectionState,
  requestAccess,
}: UseBrowserAccessRecoveryOptions): UseBrowserAccessRecoveryResult {
  const [access, setAccess] = useState<BrowserAccessResponse | null>(null);
  const [generation, setGeneration] = useState(0);
  const [state, setState] = useState<RecoveryState>('idle');
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const epochRef = useRef(0);
  const attemptRef = useRef(0);
  const startedAtRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const onlineHandlerRef = useRef<(() => void) | null>(null);
  const inFlightRef = useRef(false);
  const failedGenerationRef = useRef(-1);
  const awaitingFreshConnectionRef = useRef(false);
  const runRequestRef = useRef<(epoch: number) => void>(() => undefined);

  const clearScheduled = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = undefined;
    }
    if (onlineHandlerRef.current) {
      window.removeEventListener('online', onlineHandlerRef.current);
      onlineHandlerRef.current = null;
    }
  }, []);

  const exhaust = useCallback((key: string) => {
    clearScheduled();
    setState('exhausted');
    setErrorKey(key);
  }, [clearScheduled]);

  const scheduleRetry = useCallback((epoch: number) => {
    if (epoch !== epochRef.current || inFlightRef.current || timerRef.current) return;
    const elapsed = Date.now() - startedAtRef.current;
    if (attemptRef.current >= MAX_ATTEMPTS || elapsed >= RECOVERY_BUDGET_MS) {
      exhaust('workspace.browser.error.recoveryExhausted');
      return;
    }
    setState('recovering');
    if (!navigator.onLine) {
      if (!onlineHandlerRef.current) {
        onlineHandlerRef.current = () => {
          if (onlineHandlerRef.current) {
            window.removeEventListener('online', onlineHandlerRef.current);
            onlineHandlerRef.current = null;
          }
          runRequestRef.current(epoch);
        };
        window.addEventListener('online', onlineHandlerRef.current, { once: true });
      }
      return;
    }
    const baseDelay = Math.min(1000 * (2 ** Math.max(0, attemptRef.current - 1)), MAX_DELAY_MS);
    const jitteredDelay = Math.round(baseDelay * (0.9 + Math.random() * 0.2));
    timerRef.current = setTimeout(() => {
      timerRef.current = undefined;
      runRequestRef.current(epoch);
    }, jitteredDelay);
  }, [exhaust]);

  const runRequest = useCallback(async (epoch: number) => {
    if (
      epoch !== epochRef.current
      || !enabled
      || !workspaceId
      || inFlightRef.current
    ) return;
    if (attemptRef.current >= MAX_ATTEMPTS) {
      exhaust('workspace.browser.error.recoveryExhausted');
      return;
    }
    if (startedAtRef.current === 0) startedAtRef.current = Date.now();
    attemptRef.current += 1;
    inFlightRef.current = true;
    setState(attemptRef.current === 1 ? 'requesting' : 'recovering');
    setErrorKey(null);
    try {
      const nextAccess = await requestAccess(workspaceId);
      if (epoch !== epochRef.current) return;
      setAccess(nextAccess);
      awaitingFreshConnectionRef.current = true;
      setGeneration((current) => current + 1);
      setState('requesting');
    } catch (error) {
      if (epoch !== epochRef.current) return;
      const errorCode = error instanceof ApiError ? error.errorCode : undefined;
      const retryable = !(error instanceof ApiError)
        || error.status >= 500
        || errorCode === 'BROWSER_CONNECTIVITY_NOT_READY'
        || errorCode === 'BROWSER_CONNECTIVITY_UNAVAILABLE'
        || errorCode === 'BROWSER_NOT_READY'
        || errorCode === 'BROWSER_CREDENTIAL_ROTATING';
      if (!retryable) {
        exhaust('workspace.browser.error.credentialUnavailable');
        return;
      }
      setErrorKey(
        errorCode === 'BROWSER_CONNECTIVITY_UNAVAILABLE'
          ? 'workspace.browser.connectivity.unavailable'
          : 'workspace.browser.connectivity.preparing',
      );
      inFlightRef.current = false;
      scheduleRetry(epoch);
    } finally {
      inFlightRef.current = false;
    }
  }, [enabled, exhaust, requestAccess, scheduleRetry, workspaceId]);
  runRequestRef.current = (epoch) => {
    void runRequest(epoch);
  };

  const resetAndRequest = useCallback(() => {
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    clearScheduled();
    attemptRef.current = 0;
    startedAtRef.current = 0;
    inFlightRef.current = false;
    failedGenerationRef.current = -1;
    awaitingFreshConnectionRef.current = false;
    setAccess(null);
    setErrorKey(null);
    setState(enabled && workspaceId ? 'requesting' : 'idle');
    if (enabled && workspaceId) runRequestRef.current(epoch);
  }, [clearScheduled, enabled, workspaceId]);

  useEffect(() => {
    resetAndRequest();
    return () => {
      epochRef.current += 1;
      clearScheduled();
    };
  }, [resetAndRequest, clearScheduled]);

  useEffect(() => {
    if (connectionState === 'connecting') {
      clearScheduled();
      awaitingFreshConnectionRef.current = false;
      failedGenerationRef.current = -1;
      setState('requesting');
      return;
    }
    if (connectionState === 'connected') {
      clearScheduled();
      awaitingFreshConnectionRef.current = false;
      attemptRef.current = 0;
      startedAtRef.current = 0;
      failedGenerationRef.current = -1;
      setState('connected');
      setErrorKey(null);
      return;
    }
    if (
      connectionState === 'failed'
      && generation > 0
      && !awaitingFreshConnectionRef.current
      && failedGenerationRef.current !== generation
    ) {
      failedGenerationRef.current = generation;
      scheduleRetry(epochRef.current);
    }
  }, [clearScheduled, connectionState, generation, scheduleRetry]);

  return { access, generation, state, errorKey, retry: resetAndRequest };
}

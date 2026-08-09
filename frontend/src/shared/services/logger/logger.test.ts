import { afterEach, describe, expect, it, vi } from 'vitest';
import { createLogger } from './logger';

describe('logger', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('preserves structured context and the Error instance in console output', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const error = new Error('Request failed');
    const context = { workspaceId: 'workspace-1' };

    createLogger('WorkspaceApi').error('Unable to load workspace', {
      ...context,
      error,
    });

    expect(consoleError).toHaveBeenCalledOnce();
    expect(consoleError).toHaveBeenCalledWith(
      expect.stringContaining('[WorkspaceApi] Unable to load workspace'),
      context,
      error,
    );
  });

  it('keeps console methods, module prefixes, and development timestamps', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-02T03:04:05.678Z'));
    const consoleDebug = vi.spyOn(console, 'debug').mockImplementation(() => undefined);
    const consoleInfo = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const moduleLogger = createLogger('Contract');

    moduleLogger.debug('Debug');
    moduleLogger.info('Info');
    moduleLogger.warn('Warn');
    moduleLogger.error('Error');

    expect(consoleDebug).toHaveBeenCalledWith('03:04:05.678 [Contract] Debug');
    expect(consoleInfo).toHaveBeenCalledWith('03:04:05.678 [Contract] Info');
    expect(consoleWarn).toHaveBeenCalledWith('03:04:05.678 [Contract] Warn');
    expect(consoleError).toHaveBeenCalledWith('03:04:05.678 [Contract] Error');
  });
});

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface NormalizedContext {
  data?: unknown;
  error?: Error;
}

export interface ModuleLogger {
  debug: (message: string, context?: unknown) => void;
  info: (message: string, context?: unknown) => void;
  warn: (message: string, context?: unknown) => void;
  error: (message: string, context?: unknown) => void;
}

const isDevelopment = import.meta.env.DEV;

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' &&
  value !== null &&
  !Array.isArray(value)
);

const normalizeContext = (context: unknown): NormalizedContext => {
  if (context instanceof Error) {
    return { error: context };
  }

  if (isRecord(context) && context.error instanceof Error) {
    const { error, ...data } = context;
    return {
      data: Object.keys(data).length > 0 ? data : undefined,
      error,
    };
  }

  return { data: context };
};

const shouldLog = (level: LogLevel): boolean => (
  isDevelopment ||
  level === 'warn' ||
  level === 'error'
);

const writeLog = (
  level: LogLevel,
  module: string,
  message: string,
  context?: unknown,
): void => {
  if (!shouldLog(level)) {
    return;
  }

  const timestamp = isDevelopment
    ? new Date(Date.now()).toISOString().slice(11, 23)
    : '';
  const prefix = `[${module}]`;
  const args: unknown[] = [
    timestamp
      ? `${timestamp} ${prefix} ${message}`
      : `${prefix} ${message}`,
  ];
  const { data, error } = normalizeContext(context);

  if (data && Object.keys(data as object).length > 0) {
    args.push(data);
  }

  if (error) {
    args.push(error);
  }

  switch (level) {
    case 'debug':
      console.debug(...args);
      break;
    case 'info':
      console.log(...args);
      break;
    case 'warn':
      console.warn(...args);
      break;
    case 'error':
      console.error(...args);
      break;
  }
};

export const createLogger = (module: string): ModuleLogger => ({
  debug: (message, context) => writeLog('debug', module, message, context),
  info: (message, context) => writeLog('info', module, message, context),
  warn: (message, context) => writeLog('warn', module, message, context),
  error: (message, context) => writeLog('error', module, message, context),
});

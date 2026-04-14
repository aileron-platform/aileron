/**
 * Logger 類型定義
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

export interface LogEntry {
  level: LogLevel;
  timestamp: number;
  module: string;
  message: string;
  data?: Record<string, unknown>;
  error?: Error;
}

export type LogHandler = (entry: LogEntry) => void;

export interface ModuleLogger {
  debug: (message: string, data?: Record<string, unknown>) => void;
  info: (message: string, data?: Record<string, unknown>) => void;
  warn: (message: string, data?: Record<string, unknown>) => void;
  error: (message: string, error?: Error | unknown, data?: Record<string, unknown>) => void;
  log: (message: string, data?: Record<string, unknown>) => void;
}

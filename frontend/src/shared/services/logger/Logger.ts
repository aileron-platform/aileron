/**
 * 統一的 Logger 服務
 *
 * 用法：
 * import { createLogger } from '@/shared/services/logger';
 * const logger = createLogger('ModuleName');
 *
 * logger.debug('Debug message');
 * logger.info('Info message');
 * logger.warn('Warning message');
 * logger.error('Error message', error);
 */

import { LogLevel, LogEntry, LogHandler, ModuleLogger } from './types';

class Logger {
  private static instance: Logger;
  private level: LogLevel = LogLevel.DEBUG;
  private handlers: LogHandler[] = [];
  private isDevelopment: boolean;

  private constructor() {
    this.isDevelopment = import.meta.env.DEV;
    // 生產環境預設只顯示 WARN 以上
    if (!this.isDevelopment) {
      this.level = LogLevel.WARN;
    }
  }

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  /**
   * 設定日誌級別
   */
  setLevel(level: LogLevel): void {
    this.level = level;
  }

  /**
   * 取得當前日誌級別
   */
  getLevel(): LogLevel {
    return this.level;
  }

  /**
   * 添加日誌處理器（用於遠程日誌收集等）
   */
  addHandler(handler: LogHandler): void {
    this.handlers.push(handler);
  }

  /**
   * 移除日誌處理器
   */
  removeHandler(handler: LogHandler): void {
    const index = this.handlers.indexOf(handler);
    if (index > -1) {
      this.handlers.splice(index, 1);
    }
  }

  /**
   * 建立模組專用的 logger
   */
  createModuleLogger(module: string): ModuleLogger {
    return {
      debug: (message: string, data?: Record<string, unknown>) =>
        this.log(LogLevel.DEBUG, module, message, data),
      info: (message: string, data?: Record<string, unknown>) =>
        this.log(LogLevel.INFO, module, message, data),
      warn: (message: string, data?: Record<string, unknown>) =>
        this.log(LogLevel.WARN, module, message, data),
      error: (message: string, error?: Error | unknown, data?: Record<string, unknown>) =>
        this.logError(module, message, error, data),
      log: (message: string, data?: Record<string, unknown>) =>
        this.log(LogLevel.INFO, module, message, data),
    };
  }

  private log(
    level: LogLevel,
    module: string,
    message: string,
    data?: Record<string, unknown>
  ): void {
    if (!this.shouldLog(level)) {
      return;
    }

    const entry: LogEntry = {
      level,
      timestamp: Date.now(),
      module,
      message,
      data,
    };

    this.processEntry(entry);
  }

  private logError(
    module: string,
    message: string,
    error?: Error | unknown,
    data?: Record<string, unknown>
  ): void {
    if (!this.shouldLog(LogLevel.ERROR)) {
      return;
    }

    const entry: LogEntry = {
      level: LogLevel.ERROR,
      timestamp: Date.now(),
      module,
      message,
      data,
      error: error instanceof Error ? error : undefined,
    };

    this.processEntry(entry);
  }

  private processEntry(entry: LogEntry): void {
    // 呼叫自定義處理器
    this.handlers.forEach((handler) => {
      try {
        handler(entry);
      } catch {
        // 忽略處理器錯誤
      }
    });

    // 輸出到 console
    this.logToConsole(entry);
  }

  private logToConsole(entry: LogEntry): void {
    const prefix = `[${entry.module}]`;
    const timestamp = this.isDevelopment
      ? new Date(entry.timestamp).toISOString().slice(11, 23)
      : '';

    const args: unknown[] = [];

    if (timestamp) {
      args.push(`${timestamp} ${prefix} ${entry.message}`);
    } else {
      args.push(`${prefix} ${entry.message}`);
    }

    if (entry.data && Object.keys(entry.data).length > 0) {
      args.push(entry.data);
    }

    if (entry.error) {
      args.push(entry.error);
    }

    switch (entry.level) {
      case LogLevel.DEBUG:
        // eslint-disable-next-line no-console
        console.debug(...args);
        break;
      case LogLevel.INFO:
        // eslint-disable-next-line no-console
        console.log(...args);
        break;
      case LogLevel.WARN:
        // eslint-disable-next-line no-console
        console.warn(...args);
        break;
      case LogLevel.ERROR:
        // eslint-disable-next-line no-console
        console.error(...args);
        break;
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.level;
  }
}

// 導出單例
export const logger = Logger.getInstance();

// 導出建立模組 logger 的便利函數
export function createLogger(module: string): ModuleLogger {
  return logger.createModuleLogger(module);
}

// 導出設定函數
export function setLogLevel(level: LogLevel): void {
  logger.setLevel(level);
}

export function addLogHandler(handler: LogHandler): void {
  logger.addHandler(handler);
}

export function removeLogHandler(handler: LogHandler): void {
  logger.removeHandler(handler);
}

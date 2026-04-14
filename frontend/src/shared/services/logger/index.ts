/**
 * Logger 服務
 *
 * 用法：
 * ```typescript
 * import { createLogger } from '@/shared/services/logger';
 *
 * const logger = createLogger('MyModule');
 *
 * logger.debug('Debug info');
 * logger.info('Operation completed');
 * logger.warn('Something might be wrong');
 * logger.error('Operation failed', error);
 * ```
 */

export { LogLevel } from './types';
export type { LogEntry, LogHandler, ModuleLogger } from './types';
export {
  logger,
  createLogger,
  setLogLevel,
  addLogHandler,
  removeLogHandler,
} from './Logger';

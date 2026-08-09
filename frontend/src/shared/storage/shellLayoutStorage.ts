import { createLogger } from '@/shared/services/logger';

export type ShellCompanionPlacement = 'side' | 'bottom';

export interface ShellLayoutStoragePreferences {
  navSidebarCollapsed: boolean;
  navSidebarWidth: number;
  secondColumnCollapsed: boolean;
  secondColumnWidth: number;
  companionCollapsed: boolean;
  companionWidth: number;
  companionHeight: number;
  companionPlacement: ShellCompanionPlacement;
}

interface NumberRange {
  min: number;
  max: number;
}

export interface ShellLayoutStorageLimits {
  navSidebarWidth: NumberRange;
  secondColumnWidth: NumberRange;
  companionWidth: NumberRange;
  companionHeight: NumberRange;
}

export interface CreateShellLayoutStorageOptions {
  featureKey: string;
  limits: ShellLayoutStorageLimits;
}

export interface ShellLayoutStorage {
  load: (entityId: string) => ShellLayoutStoragePreferences | null;
  save: (entityId: string, preferences: ShellLayoutStoragePreferences) => void;
  clear: (entityId: string) => void;
}

const STORAGE_VERSION = '1';

const clamp = (value: number, range: NumberRange): number => (
  Math.max(range.min, Math.min(range.max, value))
);

const isValidPreferences = (value: unknown): value is ShellLayoutStoragePreferences => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return typeof candidate.navSidebarCollapsed === 'boolean'
    && typeof candidate.navSidebarWidth === 'number'
    && typeof candidate.secondColumnCollapsed === 'boolean'
    && typeof candidate.secondColumnWidth === 'number'
    && typeof candidate.companionCollapsed === 'boolean'
    && typeof candidate.companionWidth === 'number'
    && typeof candidate.companionHeight === 'number'
    && (candidate.companionPlacement === 'side' || candidate.companionPlacement === 'bottom');
};

export const createShellLayoutStorage = (
  options: CreateShellLayoutStorageOptions,
): ShellLayoutStorage => {
  const { featureKey, limits } = options;
  const logger = createLogger(`ShellLayoutStorage:${featureKey}`);
  const keyFor = (entityId: string): string => `shell_layout_${featureKey}_${entityId}`;

  const clear = (entityId: string): void => {
    try {
      localStorage.removeItem(keyFor(entityId));
    } catch (error) {
      logger.error(`Failed to clear shell layout for ${entityId}`, { error });
    }
  };

  const load = (entityId: string): ShellLayoutStoragePreferences | null => {
    try {
      const stored = localStorage.getItem(keyFor(entityId));
      if (!stored) {
        return null;
      }

      const parsed = JSON.parse(stored) as { version?: string; data?: unknown };

      if (parsed.version !== STORAGE_VERSION || !isValidPreferences(parsed.data)) {
        logger.warn(`Shell layout storage invalid for ${entityId}, clearing cache`);
        clear(entityId);
        return null;
      }

      const data = parsed.data;

      return {
        ...data,
        navSidebarWidth: clamp(data.navSidebarWidth, limits.navSidebarWidth),
        secondColumnWidth: clamp(data.secondColumnWidth, limits.secondColumnWidth),
        companionWidth: clamp(data.companionWidth, limits.companionWidth),
        companionHeight: clamp(data.companionHeight, limits.companionHeight),
      };
    } catch (error) {
      logger.error(`Failed to load shell layout for ${entityId}`, { error });
      clear(entityId);
      return null;
    }
  };

  const save = (entityId: string, preferences: ShellLayoutStoragePreferences): void => {
    try {
      localStorage.setItem(keyFor(entityId), JSON.stringify({ version: STORAGE_VERSION, data: preferences }));
    } catch (error) {
      logger.error(`Failed to save shell layout for ${entityId}`, { error });
    }
  };

  return { load, save, clear };
};

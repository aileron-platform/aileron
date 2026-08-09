import type { HookDialogData } from '@/shared/components/hook-workflow';

export interface HookSource {
  list(): Promise<HookDialogData[]>;
  save(entry: HookDialogData, previous?: HookDialogData | null): Promise<void>;
  remove(entry: HookDialogData): Promise<void>;
  featureEnablement?: {
    isEnabled(scope?: 'project' | 'user'): Promise<boolean>;
    enable(scope?: 'project' | 'user'): Promise<void>;
    disable?(scope?: 'project' | 'user'): Promise<void>;
  };
  pluginTrust?: {
    update(entry: HookDialogData, trusted: boolean): Promise<void>;
  };
}

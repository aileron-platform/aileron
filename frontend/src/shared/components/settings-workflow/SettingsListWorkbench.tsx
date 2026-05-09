import React from 'react';
import { Inbox } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

export interface SettingsListWorkbenchI18nKeys {
  emptyTitle?: string;
  emptyDescription?: string;
}

export interface SettingsListWorkbenchProps<TItem> {
  items: TItem[];
  getItemKey: (item: TItem, index: number) => React.Key;
  card: (item: TItem, index: number) => React.ReactNode;
  dialog?: React.ReactNode;
  isLoading?: boolean;
  loading?: React.ReactNode;
  emptyStateI18nKey?: string;
  i18nBaseKey?: string;
  i18nKeys?: SettingsListWorkbenchI18nKeys;
  className?: string;
  listClassName?: string;
}

export function SettingsListWorkbench<TItem>({
  items,
  getItemKey,
  card,
  dialog,
  isLoading = false,
  loading,
  emptyStateI18nKey,
  i18nBaseKey = 'workspace.agentSettings.settings.list',
  i18nKeys,
  className,
  listClassName,
}: SettingsListWorkbenchProps<TItem>) {
  const { t } = useI18n();
  const emptyTitleKey = i18nKeys?.emptyTitle ?? emptyStateI18nKey ?? `${i18nBaseKey}.empty.title`;
  const emptyDescriptionKey = i18nKeys?.emptyDescription
    ?? (emptyStateI18nKey ? `${emptyStateI18nKey}.description` : `${i18nBaseKey}.empty.description`);

  return (
    <>
      <div className={cn('space-y-4', className)}>
        {isLoading ? (
          loading
        ) : items.length > 0 ? (
          <div className={cn('space-y-4', listClassName)}>
            {items.map((item, index) => (
              <React.Fragment key={getItemKey(item, index)}>
                {card(item, index)}
              </React.Fragment>
            ))}
          </div>
        ) : (
          <div className="grid min-h-48 place-content-center rounded-lg border border-dashed border-border px-6 py-10 text-center">
            <div className="mx-auto mb-3 rounded-full bg-muted p-3 text-muted-foreground">
              <Inbox className="h-5 w-5" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-foreground">{t(emptyTitleKey)}</p>
            <p className="mt-1 text-sm text-muted-foreground">{t(emptyDescriptionKey)}</p>
          </div>
        )}
      </div>

      {dialog ?? null}
    </>
  );
}

export default SettingsListWorkbench;

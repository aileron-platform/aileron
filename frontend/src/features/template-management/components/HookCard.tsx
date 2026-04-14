import { Badge } from '@/shared/components/ui/badge';
import { Edit, Trash2, Terminal } from 'lucide-react';
import { getEventDescription } from '@/features/template-management/features/template-editor/constants/hookEvents';
import { useI18n } from '@/shared/hooks/useI18n';
import type { HookFormValue } from '@/features/template-management/features/template-editor/formTypes';

interface HookCardProps {
  hook: HookFormValue;
  mode: 'view' | 'edit';
  onEdit?: (hook: HookFormValue) => void;
  onDelete?: (hookId: string) => void;
}

export default function HookCard({
  hook,
  mode,
  onEdit,
  onDelete
}: HookCardProps) {
  const { t } = useI18n();

  const matchers = hook.matchers ?? [];
  const totalMatchers = matchers.length;
  const totalCommands = matchers.reduce((acc, matcher) => acc + (matcher.hooks?.length ?? 0), 0);
  const eventLabel = getEventDescription(hook.event, t);

  const handleEdit = () => {
    if (mode === 'edit' && onEdit) {
      onEdit(hook);
    }
  };

  const handleDelete = () => {
    if (mode === 'edit' && onDelete) {
      onDelete(hook.localId);
    }
  };

  return (
    <div className="relative rounded-lg border border-border bg-background p-6">
      <div className="flex items-start">
        <div className="min-w-0 flex-1">
          {/* 事件名稱 */}
          <div className="mb-3">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-foreground">{eventLabel}</h3>
            </div>
          </div>

          {/* 匹配器列表 */}
          <div className="mb-4">
            <div className="mb-3 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-muted-foreground">
                {t('template.editor.hooks.dialog.matchers.title')}
              </span>
            </div>
            <div className="space-y-2">
              {matchers.map((matcher, matcherIndex) => {
                const matcherHooks = matcher.hooks ?? [];
                return (
                  <div key={matcherIndex} className="rounded-lg bg-muted/50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {t('template.editor.hooks.card.matcherLabel')}
                      </span>
                      <code className="rounded bg-muted px-1 text-xs">{matcher.matcher}</code>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {t('template.editor.hooks.card.actionsCount', {
                        count: matcherHooks.length,
                      })}
                    </span>
                  </div>
                  {matcherHooks.slice(0, 2).map((exec, execIndex) => (
                    <div key={execIndex} className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                      <div className="mb-1 flex items-center gap-2">
                        <Badge variant="outline" className="px-1 py-0 text-xs">
                          {t('template.editor.hooks.card.execution.type.command')}
                        </Badge>
                        {exec.timeout && (
                          <span className="text-muted-foreground">
                            {exec.timeout}s
                          </span>
                        )}
                      </div>
                      <p className="truncate font-mono text-muted-foreground">
                        {exec.command?.trim()
                          ? exec.command
                          : t('template.editor.hooks.card.execution.empty')}
                      </p>
                    </div>
                  ))}
                  {matcherHooks.length > 2 && (
                    <div className="text-xs italic text-muted-foreground">
                      {t('template.editor.hooks.card.moreActions', {
                        count: matcherHooks.length - 2,
                      })}
                    </div>
                  )}
                </div>
              );
              })}
            </div>
          </div>

          {/* 統計資訊 */}
          <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span>
              {t('template.editor.hooks.card.summary.matchers', {
                count: totalMatchers,
              })}
            </span>
            <span>
              {t('template.editor.hooks.card.summary.commands', {
                count: totalCommands,
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Action Buttons - 僅編輯模式顯示 */}
      {mode === 'edit' && (
        <div className="absolute top-4 right-4 flex items-center gap-2">
          <button
            type="button"
            className="rounded-md p-2 transition-colors hover:bg-muted"
            onClick={handleEdit}
            title={t('template.editor.hooks.card.actions.editTooltip', { event: eventLabel })}
          >
            <Edit className="h-4 w-4 text-muted-foreground" />
            <span className="sr-only">{t('template.editor.hooks.card.actions.editSrLabel')}</span>
          </button>
          <button
            type="button"
            className="rounded-md p-2 transition-colors hover:bg-muted"
            onClick={handleDelete}
            title={t('template.editor.hooks.card.actions.deleteTooltip', { event: eventLabel })}
          >
            <Trash2 className="h-4 w-4 text-muted-foreground" />
            <span className="sr-only">{t('template.editor.hooks.card.actions.deleteSrLabel')}</span>
          </button>
        </div>
      )}
    </div>
  );
}

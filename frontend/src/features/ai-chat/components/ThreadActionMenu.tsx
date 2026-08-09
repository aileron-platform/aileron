import type { ReactNode } from 'react';
import { Archive, Copy, MoreHorizontal, Trash2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useShowInitMessages } from '../hooks/useShowInitMessages';

interface ThreadActionMenuProps {
  thread: { id: string; archived: boolean } | null;
  onArchive?: (threadId: string) => void;
  onDelete?: (threadId: string) => void;
  onCopyThreadId?: (threadId: string) => void;
  includeCopyThreadId?: boolean;
  includeDisplaySettings?: boolean;
  disabled?: boolean;
  triggerClassName?: string;
}

const defaultTriggerClassName =
  'inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50';

const menuIconClassName = 'mr-2 h-4 w-4';

const callWithThread = (
  threadId: string | null,
  callback: ((threadId: string) => void) | undefined,
) => {
  if (!threadId || !callback) return;
  callback(threadId);
};

const ActionItem = ({
  children,
  destructive = false,
  disabled,
  icon,
  onSelect,
}: {
  children: ReactNode;
  destructive?: boolean;
  disabled: boolean;
  icon: ReactNode;
  onSelect: () => void;
}) => (
  <DropdownMenuItem
    disabled={disabled}
    className={destructive ? 'text-destructive focus:text-destructive' : undefined}
    onSelect={onSelect}
  >
    {icon}
    {children}
  </DropdownMenuItem>
);

export const ThreadActionMenu = ({
  thread,
  onArchive,
  onDelete,
  onCopyThreadId,
  includeCopyThreadId = false,
  includeDisplaySettings = false,
  disabled = false,
  triggerClassName,
}: ThreadActionMenuProps) => {
  const { t } = useI18n();
  const [showInitMessages, setShowInitMessages] = useShowInitMessages();
  const threadId = thread?.id ?? null;
  const itemDisabled = disabled || !threadId;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t('aiChat.threadActions.menu')}
          className={cn(defaultTriggerClassName, triggerClassName)}
          disabled={disabled}
          onClick={(event) => event.stopPropagation()}
        >
          <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44" onClick={(event) => event.stopPropagation()}>
        {onArchive && !thread?.archived && (
          <ActionItem
            disabled={itemDisabled}
            icon={<Archive className={menuIconClassName} aria-hidden="true" />}
            onSelect={() => callWithThread(threadId, onArchive)}
          >
            {t('aiChat.threadActions.archive')}
          </ActionItem>
        )}
        {onDelete && (
          <ActionItem
            destructive
            disabled={itemDisabled}
            icon={<Trash2 className={menuIconClassName} aria-hidden="true" />}
            onSelect={() => callWithThread(threadId, onDelete)}
          >
            {t('aiChat.threadActions.delete')}
          </ActionItem>
        )}
        {includeCopyThreadId && (
          <>
            <DropdownMenuSeparator />
            <ActionItem
              disabled={itemDisabled || !onCopyThreadId}
              icon={<Copy className={menuIconClassName} aria-hidden="true" />}
              onSelect={() => callWithThread(threadId, onCopyThreadId)}
            >
              {t('aiChat.threadActions.copyThreadId')}
            </ActionItem>
          </>
        )}
        {includeDisplaySettings && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={showInitMessages}
              onSelect={(event) => {
                event.preventDefault();
                setShowInitMessages(!showInitMessages);
              }}
            >
              {t('aiChat.threadActions.showInitMessages')}
            </DropdownMenuCheckboxItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

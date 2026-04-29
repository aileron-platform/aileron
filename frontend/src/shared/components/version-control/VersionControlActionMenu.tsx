import React, { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, MoreHorizontal, RefreshCw, Settings } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

type VersionControlActionId = 'refresh' | 'fetch' | 'pull' | 'push' | 'remoteSettings';

export interface VersionControlActionMenuItem {
  id: VersionControlActionId;
  onClick: () => void;
  disabled?: boolean;
}

interface VersionControlActionMenuProps {
  actions: VersionControlActionMenuItem[];
  disabled?: boolean;
  className?: string;
}

const actionIcons: Record<VersionControlActionId, React.ReactNode> = {
  refresh: <RefreshCw className="h-3 w-3" />,
  fetch: <RefreshCw className="h-3 w-3" />,
  pull: <ArrowDown className="h-3 w-3" />,
  push: <ArrowUp className="h-3 w-3" />,
  remoteSettings: <Settings className="h-3 w-3" />,
};

export const VersionControlActionMenu: React.FC<VersionControlActionMenuProps> = ({
  actions,
  disabled = false,
  className,
}) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  return (
    <div ref={menuRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="p-1 hover:bg-muted/30 rounded transition-colors disabled:opacity-50"
        aria-label={t('shared.versionControl.actions.menu.label')}
        title={t('shared.versionControl.actions.menu.label')}
        disabled={disabled}
      >
        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-1 w-40 rounded-md border border-border bg-background shadow-lg">
          <div className="py-1">
            {actions.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  action.onClick();
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={action.disabled}
              >
                {actionIcons[action.id]}
                {t(`shared.versionControl.actions.${action.id}.label`)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VersionControlActionMenu;

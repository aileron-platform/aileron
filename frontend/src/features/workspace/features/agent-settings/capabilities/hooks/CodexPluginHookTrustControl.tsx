import React from 'react';
import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Label } from '@/shared/components/ui/label';
import { Switch } from '@/shared/components/ui/switch';
import { useI18n } from '@/shared/hooks/useI18n';
import type { HookDialogData } from '@/shared/components/hook-workflow';

interface CodexPluginHookTrustControlProps {
  hook: HookDialogData & {
    pluginId: string;
    trustState: 'trusted' | 'untrusted' | 'modified' | 'mixed';
    trusted: boolean;
    effective: boolean;
    trustRevision: string;
  };
  disabled?: boolean;
  i18nNamespace: string;
  onTrustedChange(hook: HookDialogData, trusted: boolean): void;
}

const CodexPluginHookTrustControl: React.FC<CodexPluginHookTrustControlProps> = ({
  hook,
  disabled = false,
  i18nNamespace,
  onTrustedChange,
}) => {
  const { t } = useI18n();
  const Icon = hook.trusted ? ShieldCheck : ShieldAlert;

  return (
    <section
      aria-label={t(`${i18nNamespace}.hooks.pluginTrust.title`)}
      className="mt-4 rounded-md border border-primary/20 bg-primary/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
            <h4 className="text-sm font-semibold">
              {t(`${i18nNamespace}.hooks.pluginTrust.title`)}
            </h4>
            <Badge variant="outline">
              {t(`${i18nNamespace}.hooks.pluginTrust.states.${hook.trustState}`)}
            </Badge>
            <Badge variant={hook.effective ? 'default' : 'secondary'}>
              {t(`${i18nNamespace}.hooks.pluginTrust.effective.${hook.effective ? 'active' : 'inactive'}`)}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(`${i18nNamespace}.hooks.pluginTrust.description`)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(`${i18nNamespace}.hooks.pluginTrust.newThreadRequired`)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor={`plugin-hook-trust-${hook.id}`} className="text-xs">
            {t(`${i18nNamespace}.hooks.pluginTrust.fields.trusted`)}
          </Label>
          <Switch
            id={`plugin-hook-trust-${hook.id}`}
            checked={hook.trusted}
            onCheckedChange={(trusted) => onTrustedChange(hook, trusted)}
            disabled={disabled}
            aria-label={t(`${i18nNamespace}.hooks.pluginTrust.fields.trusted`)}
          />
        </div>
      </div>
    </section>
  );
};

export default CodexPluginHookTrustControl;

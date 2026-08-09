import React from 'react';
import { ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { DocumentSourceBadge } from '@/shared/components/document-resource';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  buildPluginDetailHref,
  type PluginResourceProvider,
  type PluginSettingsResourceKind,
} from '../../model/pluginResources';

interface PluginResourceMetadataProps {
  provider: PluginResourceProvider;
  resource: PluginSettingsResourceKind;
  workspaceId: string;
  pluginId?: string | null;
  pluginName?: string | null;
  marketplaceId?: string | null;
  enabled?: boolean;
  readOnly?: boolean;
  relativeSourcePath?: string | null;
  compact?: boolean;
}

export const PluginResourceMetadata: React.FC<PluginResourceMetadataProps> = ({
  provider,
  resource,
  workspaceId,
  pluginId,
  pluginName,
  marketplaceId,
  enabled,
  readOnly,
  relativeSourcePath,
  compact = false,
}) => {
  const { t } = useI18n();

  if (!pluginId) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <DocumentSourceBadge
        source={{
          type: 'plugin',
          label: t('workspace.agentSettings.pluginResources.badges.pluginSource'),
          pluginName: pluginName ?? pluginId,
          marketplaceName: marketplaceId ?? undefined,
        }}
      />
      {readOnly ? (
        <Badge variant="outline" className="text-[11px]">
          {t('workspace.agentSettings.pluginResources.badges.readOnly')}
        </Badge>
      ) : null}
      {typeof enabled === 'boolean' ? (
        <Badge variant={enabled ? 'default' : 'secondary'} className="text-[11px]">
          {t(
            enabled
              ? 'workspace.agentSettings.pluginResources.badges.enabled'
              : 'workspace.agentSettings.pluginResources.badges.disabled',
          )}
        </Badge>
      ) : null}
      {relativeSourcePath ? (
        <Badge
          variant="outline"
          className="max-w-full font-mono text-[11px]"
          title={relativeSourcePath}
        >
          <span className="truncate">{relativeSourcePath}</span>
        </Badge>
      ) : null}
      <Button
        asChild
        variant="ghost"
        size="sm"
        className={compact ? 'h-6 px-1.5 text-[11px]' : 'h-7 px-2 text-xs'}
      >
        <Link
          to={buildPluginDetailHref({
            workspaceId,
            provider,
            pluginId,
            resource,
          })}
        >
          <ExternalLink className="mr-1 h-3 w-3" />
          {t('workspace.agentSettings.pluginResources.actions.viewPlugin')}
        </Link>
      </Button>
    </div>
  );
};
